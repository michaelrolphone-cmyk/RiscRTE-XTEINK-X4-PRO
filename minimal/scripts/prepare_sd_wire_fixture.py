#!/usr/bin/env python3
"""Point the reference card-wire fixture at the production SD protocol header."""
import argparse
from pathlib import Path


def prepare(output):
    source = Path(__file__).resolve().parents[2] / 'Drivers/x4pro_board/x4pro_proto.h'
    text = source.read_text()
    old = '#include "../storage_fatfs/sd_protocol.h"'
    if text.count(old) != 1:
        raise ValueError('Reference protocol include changed')
    (Path(output) / 'x4pro_proto.h').write_text(text.replace(old, '#include "sd_protocol.h"'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    prepare(parser.parse_args().output)
