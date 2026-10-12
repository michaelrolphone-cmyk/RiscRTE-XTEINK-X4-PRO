"""Physical SPIFFS placement only; original file bytes and admission are intact."""
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import tempfile

# Follow the measured X4 foreground closure after the immutable bootstrap pair.
# These are placement hints, not provider activation or authorization changes.
FOREGROUND = ('x4pro-frontlight','x4pro-uc8279-fast','alarm-service','twatch-ble',
 'x4pro-i2c','x4pro-battery','telemetry-battery','ble-telemetry','telemetry-broadcast',
 'x4pro-gt911','x4pro-power','x4pro-power-buttons','s3-radio-iq-v1','contexts-service',
 'x4pro-rtc','installed-apps','wifi')


def ordered_paths(store):
    boot=json.loads(store['boot.json'])
    paths=['boot.json',boot['board']]
    paths.extend(row['manifest'] for row in boot['drivers'])
    cohort=False
    for row in boot['app_capabilities']:
        paths.append(row['manifest'])
        if not cohort and any(g['capability']=='runtime.retained-wake' for g in row['grants']):
            paths.append('cohort.json');cohort=True
    paths.append(boot['default_app'])
    providers={}
    for row in boot['drivers']:
        manifest=json.loads(store[row['manifest']])
        name=str(PurePosixPath(row['manifest']).parent/manifest['file_name'])
        providers[manifest['id']]=name
        if 'image_source' not in row:paths.append(name)
    paths.extend(providers[name] for name in FOREGROUND if name in providers)
    paths.extend(sorted(store))
    order=list(dict.fromkeys(paths))
    if len(order)!=len(store) or set(order)!=set(store):
        raise ValueError('Boot order references absent or additional files')
    return order


def build(store, original_build):
    # Reuse the hash-pinned producer's complete input and format validation.
    # No dependency source is edited, and no SDK/index implementation is added.
    baseline,record=original_build(store)
    import current_bootfs as base
    order=ordered_paths(store)
    spec=importlib.util.spec_from_file_location('x4_ordered_spiffsgen',base.GENERATOR)
    generator=importlib.util.module_from_spec(spec);spec.loader.exec_module(generator)
    fs=generator.SpiffsFS(base.IMAGE_SIZE,generator.SpiffsBuildConfig(**base.CONFIG))
    with tempfile.TemporaryDirectory(prefix='x4-boot-order-') as tmp:
        for index,name in enumerate(order):
            source=Path(tmp)/str(index);source.write_bytes(store[name])
            fs.create_file('/'+name,str(source))
    free_blocks=fs.remaining_blocks
    image=fs.to_binary()
    if (len(image)!=len(baseline) or free_blocks!=record['empty_blocks'] or
            len(fs.blocks)!=record['occupied_blocks'] or base.read_image(image,len(image))!=store):
        raise ValueError('Boot-order image changed contents, geometry or free-block reserve')
    record.update(order='Runtime metadata order, default/bootstrap, foreground hints, remaining ASCII paths',
                  ordered_paths=order,sha256=hashlib.sha256(image).hexdigest(),
                  alphabetical_reference_sha256=hashlib.sha256(baseline).hexdigest(),
                  order_recipe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    return image,record
