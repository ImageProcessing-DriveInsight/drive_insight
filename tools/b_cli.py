"""Run with python -m tools.b_cli from the project root."""
import argparse
from src.io import extract_eval_set
from src.adaptive import enhance_frames, enhance_video
from src.adaptive.pipeline import load_callable
from src.package import build_package


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    extract = commands.add_parser('extract')
    extract.add_argument('--csv', default='data/eval_set.csv')
    frames = commands.add_parser('frames')
    frames.add_argument('--apply-ops', default='src.dip.fixed:apply_ops')
    video = commands.add_parser('video')
    video.add_argument('clip')
    video.add_argument('--mode', choices=['fixed', 'adaptive'], required=True)
    video.add_argument('--apply-ops', default='src.dip.fixed:apply_ops')
    video.add_argument('--fixed', default='src.dip.fixed:fixed_enhance')
    package = commands.add_parser('package')
    package.add_argument('clip_id')
    args = p.parse_args()
    if args.command == 'extract':
        print(extract_eval_set(args.csv))
    elif args.command == 'frames':
        print(f'{len(enhance_frames(apply_ops=load_callable(args.apply_ops)))} frames processed')
    elif args.command == 'video':
        kwargs = {'fixed_enhance': load_callable(args.fixed)} if args.mode == 'fixed' else {'apply_ops': load_callable(args.apply_ops)}
        print(enhance_video(args.clip, args.mode, **kwargs))
    else:
        print(build_package(args.clip_id))

if __name__ == '__main__':
    main()
