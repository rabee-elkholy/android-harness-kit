"""Register disjoint dispatch batches on one fresh package without losing reports."""
import time

from _evidence import locked
from _hook_state import read_verdict_record, write_verdict_record, state_path
from _review_contract import package_valid, required_keys


def register_batch(pkg12: str, reviewers: list[str], conversation: str) -> bool:
    """Return True for first batch. Raise before mutation on invalid input."""
    with locked(state_path().parent / ('record-' + pkg12 + '.lock')):
        record = read_verdict_record(pkg12)
        if not record or not package_valid(record):
            raise ValueError('Batch requires a current, complete schema-v3 package')
        required = set(required_keys(record))
        if not reviewers or len(reviewers) != len(set(reviewers)) or not set(reviewers) <= required:
            raise ValueError('Batch must contain distinct required reviewers')
        batches = record.get('review_batches', [])
        if batches and any(b['conversation'] != conversation for b in batches):
            raise ValueError('Continue review batches in their original conversation')
        dispatched = {key for batch in batches for key in batch['reviewers']}
        if dispatched.intersection(reviewers):
            raise ValueError('Reviewer already dispatched for this package; record its result or regenerate')
        if record.get('verdict') in ('APPROVED', 'EXPIRED'):
            raise ValueError('Package review is already complete or expired')
        batches.append({'reviewers': reviewers, 'conversation': conversation, 'at': time.time()})
        record['review_batches'] = batches
        record['review_execution'] = 'structured_batches'
        if not write_verdict_record(pkg12, record):
            raise ValueError('Could not persist batch')
        return len(batches) == 1
