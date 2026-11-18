"""All-or-nothing directory publication for cooperating MaskLedger writers.

The sibling lock prevents two tool instances publishing the same destination.
Publication retries a bounded number of times when the platform reports a
transient access denial on the freshly written staging directory; no specific
cause is assumed. This is not protection against hostile filesystem
replacement or power loss.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import time
from .errors import InputError

_PUBLISH_DELAYS=(0,0.05,0.1,0.2,0.4,0.8)


def _publish(staged,destination):
    for attempt,delay in enumerate(_PUBLISH_DELAYS,1):
        if delay:time.sleep(delay)
        if os.path.lexists(destination):raise InputError('output appeared before publication')
        try:
            staged.rename(destination);return
        except FileExistsError as exc:
            raise InputError('output appeared before publication') from exc
        except PermissionError:
            if attempt==len(_PUBLISH_DELAYS):raise


@contextmanager
def output_transaction(destination):
    destination=Path(destination).absolute()
    if os.path.lexists(destination):
        raise InputError('output already exists; choose a new directory')
    destination.parent.mkdir(parents=True,exist_ok=True)
    lock=destination.with_name('.'+destination.name+'.lock')
    try:
        descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError as exc:
        raise InputError('another output transaction holds this destination') from exc
    os.close(descriptor)
    try:
        if os.path.lexists(destination):raise InputError('output appeared during reservation')
        with tempfile.TemporaryDirectory(prefix='.'+destination.name+'.stage-',dir=destination.parent) as temporary:
            staged=Path(temporary)/'payload';staged.mkdir()
            yield staged
            _publish(staged,destination)
    finally:
        lock.unlink(missing_ok=True)
