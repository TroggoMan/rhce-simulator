"""
Actions the browser task panel can perform on a live Session.

Ported from rhcsa-simulator's panel_control.py, with one structural
simplification: that version serialises graded results into a flat dict
because its ExamSession only keeps them around that way. RHCE's Session
(core/engine.py) already holds `self.tasks` (live Task objects) and
`self.results` (task_id -> ValidationResult) for the session's whole
lifetime, so this works directly off those — no serialise/deserialise
round trip, and disputes reuse core/dispute.py's task+result API unchanged
from the terminal `d <n>` path.

THREADING
---------
Requests arrive on HTTP worker threads. Validation runs real
ansible-playbook subprocesses and mutates session state, so it must not
happen there — request_validate() only sets an Event, and the session's
own input loop (core/engine.py) polls it between prompts and does the
actual work. That keeps a single grader no matter which button was pressed.

Reset is the opposite case: destructive, so it refuses while any task is
still unvalidated, and requires the caller to confirm.
"""

import logging
import threading

logger = logging.getLogger(__name__)


class PanelController:
    """Bridge between the HTTP panel and a live Session."""

    def __init__(self, session):
        self.session = session
        # Set by the panel, consumed by the session's own input loop.
        self.submit_requested = threading.Event()
        self.quit_requested = threading.Event()
        self._dispute_lock = threading.Lock()

    # -- lifecycle -------------------------------------------------------

    def request_quit(self):
        """Ask the session to end, same as typing 'q' in the terminal.

        Only meaningful when nothing is driving the terminal loop (browser-
        only sessions started from --browser) — a session with someone
        actually typing at it can just type 'q'.
        """
        self.quit_requested.set()
        logger.info("panel requested quit")
        return {'ok': True}

    # -- grading -------------------------------------------------------

    def request_validate(self):
        """Ask the session to grade every unvalidated task. Idempotent."""
        status = getattr(self.session, 'panel_status', 'in_progress')
        if status in ('validating', 'complete'):
            return {'queued': False, 'status': status,
                    'message': 'Already submitted'}
        self.session.panel_status = 'validating'
        self.submit_requested.set()
        logger.info("panel requested validation")
        return {'queued': True, 'status': 'validating'}

    # -- disputes --------------------------------------------------------

    def file_dispute(self, task_id, check_names, argument, submit=True):
        """Raise a checker dispute for one task.

        The local report is written before any network call and kept even
        if submitting fails, so evidence is never lost to a flaky
        connection. The AI reviewer's verdict comes back as a comment on
        the GitHub issue — it does not flow back into the simulator, so
        the caller gets the issue URL to follow instead.
        """
        from core import dispute

        if not task_id:
            return {'ok': False, 'error': 'task_id is required'}

        task = self._task_for(task_id)
        result = (self.session.results or {}).get(task_id)
        if task is None or result is None:
            return {'ok': False,
                    'error': f'No graded result for {task_id} to dispute. '
                             f'Submit for grading first.'}

        with self._dispute_lock:
            try:
                artifacts = dispute.collect_artifacts(task)
                evidence = dispute.collect_evidence(task.category)
                body = dispute.build_report(task, result, argument,
                                            artifacts, evidence,
                                            disputed_checks=check_names)
                path = dispute.save_report(task, body)
            except Exception as e:
                logger.warning("dispute report failed: %s", e)
                return {'ok': False, 'error': f'Could not build report: {e}'}

            outcome = {'ok': True, 'saved_to': path, 'submitted': False,
                      'issue_url': None}

            if not submit:
                outcome['message'] = ('Saved locally. Not submitted — no '
                                      'GitHub issue was opened.')
                return outcome

            if not dispute.gh_available():
                outcome['message'] = (
                    'Saved locally. The GitHub CLI (gh) is not available or '
                    'not authenticated, so no issue was opened. The report '
                    'is complete and can be filed later.')
                return outcome

            try:
                ok, info = dispute.submit_issue(task, path)
            except Exception as e:
                logger.warning("dispute submit failed: %s", e)
                ok, info = False, str(e)

            outcome['submitted'] = bool(ok)
            if ok:
                outcome['issue_url'] = info
                outcome['message'] = (
                    'Issue opened. The AI reviewer posts its verdict as a '
                    'comment there — it does not appear in the simulator.')
            else:
                outcome['message'] = (
                    f'Saved locally, but submitting failed: {info}. The '
                    f'evidence is preserved at {path}.')
            return outcome

    def list_disputes(self):
        """Reports filed on this box, newest first.

        Disputes are otherwise fire-and-forget — there is no command to
        list what you have filed — so the panel showing them is the only
        place that gap is closed. Verdicts still live on GitHub.
        """
        import os
        from core import dispute

        entries = []
        try:
            names = sorted(os.listdir(dispute.DISPUTE_DIR), reverse=True)
        except OSError:
            names = []
        for name in names:
            if not name.endswith('.md'):
                continue
            path = os.path.join(dispute.DISPUTE_DIR, name)
            try:
                stamp = os.path.getmtime(path)
            except OSError:
                stamp = 0
            entries.append({'file': name, 'path': path, 'mtime': stamp})
        return {'disputes': entries, 'dir': dispute.DISPUTE_DIR}

    # -- lab reset ---------------------------------------------------------

    def reset_lab(self, confirm=False):
        """Rebuild the managed nodes from a clean image/snapshot.

        Destructive, so it is gated twice: the caller must pass confirm,
        and it refuses outright while any task remains unvalidated —
        resetting mid-session would destroy the state the candidate is
        about to be graded on, and a stray request must not be able to do
        that. Unlike rhcsa-simulator (one box, python-native reset), this
        shells out to scripts/lab-reset.sh, which auto-detects Docker vs
        Vagrant and force-recreates the nodes; there is no in-process
        equivalent because the nodes are not this process.
        """
        tasks = getattr(self.session, 'tasks', None) or []
        results = getattr(self.session, 'results', None) or {}
        unvalidated = [t for t in tasks if t.id not in results]
        if unvalidated:
            return {'ok': False,
                    'error': f'{len(unvalidated)} task(s) not yet validated. '
                             f'Submit for grading first — resetting now '
                             f'would destroy the state being graded.'}
        if not confirm:
            return {'ok': False, 'error': 'confirmation required'}

        import subprocess
        from pathlib import Path

        script = Path(__file__).resolve().parent.parent / 'scripts' / 'lab-reset.sh'
        if not script.exists():
            return {'ok': False,
                    'error': f'{script} not found — reset the lab manually '
                             f'(scripts/lab-reset.sh or scripts/'
                             f'vm-lab-teardown.sh + vm-lab-setup.sh).'}
        try:
            proc = subprocess.run(['bash', str(script)], capture_output=True,
                                  text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return {'ok': False,
                    'error': 'lab-reset.sh timed out after 5 minutes.'}
        except Exception as e:
            logger.warning("panel lab reset failed: %s", e)
            return {'ok': False, 'error': str(e)}

        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or '').strip().splitlines()[-5:]
            return {'ok': False, 'error': 'lab-reset.sh failed: ' +
                    ' / '.join(tail)}
        logger.info("panel reset the lab environment")
        return {'ok': True,
                'message': 'Managed nodes rebuilt. Your own inventory/'
                           'ansible.cfg/automation user are gone with '
                           'them — that is the whole point of a reset.'}

    # -- helpers -------------------------------------------------------

    def _task_for(self, task_id):
        for task in getattr(self.session, 'tasks', None) or []:
            if getattr(task, 'id', None) == task_id:
                return task
        return None
