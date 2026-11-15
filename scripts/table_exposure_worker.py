"""Isolated labelled CUDART-only exposure; fixture lives through Runtime unload."""
import argparse
import os
from pathlib import Path
import sys
import traceback


if __name__=='__main__':
    try:
        if not sys.flags.isolated or not sys.flags.no_site:raise ValueError('isolated no-site startup required')
        sys.path.append(str(Path(__file__).resolve().parent));sys.dont_write_bytecode=True
        from table_exposure_observer import FixtureOwner,ExposureObserver
        from real_bootstrap_worker import main
        p=argparse.ArgumentParser();p.add_argument('mode',choices=('intervention','intervention12090'));p.add_argument('--fixture-manifest',type=Path,required=True);args=p.parse_args()
        owner=FixtureOwner(args.fixture_manifest,Path.cwd()/'tables.dll')
        def factory(provider,**kwargs):return ExposureObserver(provider,owner=owner,**kwargs)
        def finish(mode,value):
            if value.get('runtime_unload')!=dict(free_succeeded=True,module_absent=True):raise ValueError('Runtime still loaded before fixture teardown')
            value['scope']='ct_cudart_table_exposure';value['fixture_sha256']=owner.sha
            value['fixture_before']=owner.initial;value['fixture_prefix']=owner.prefix_state
            value['fixture_after_runtime']=owner.state()
            value['fixture_unload']=owner.close()
            if value['fixture_after_runtime']!=dict(mask=0,stopped=0,reserved=0):value['callback_failures'].append('private_table_callback')
            return value
        sys.argv=[sys.argv[0],args.mode]
        code=main(observer_type=factory,result_hook=finish)
    except BaseException:
        traceback.print_exc(file=sys.stderr);code=1
    sys.stdout.flush();sys.stderr.flush();os._exit(code)
