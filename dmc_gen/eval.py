import os
from copy import deepcopy

import augmentations
import gym
import numpy as np
import torch
from arguments import parse_args, Args
from tqdm import tqdm

import utils
from dmc_gen.algorithms import make_agent
from dmc_gen.wrappers import make_env
from video import VideoRecorder


def evaluate(env, agent, video, num_episodes, eval_mode, adapt=False):
    episode_rewards = []
    for i in tqdm(range(num_episodes)):
        if adapt:
            ep_agent = deepcopy(agent)
            ep_agent.init_pad_optimizer()
        else:
            ep_agent = agent
        obs = env.reset()
        video.init(enabled=True)
        done = False
        episode_reward = 0
        while not done:
            with utils.Eval(ep_agent):
                action = ep_agent.select_action(obs)
            next_obs, reward, done, _ = env.step(action)
            video.record(env, eval_mode)
            episode_reward += reward
            if adapt:
                ep_agent.update_inverse_dynamics(*augmentations.prepare_pad_batch(obs, next_obs, action))
            obs = next_obs

        video.save(f'eval_{eval_mode}_{i}.mp4')
        episode_rewards.append(episode_reward)

    return np.mean(episode_rewards)


def main(args):
    # Set seed
    utils.set_seed_everywhere(args.seed)

    # Initialize environments
    gym.logger.set_level(40)
    env = make_env(
        domain_name=args.domain,
        task_name=args.task,
        seed=args.seed + 42,
        episode_length=args.episode_length,
        action_repeat=args.action_repeat,
        mode=args.Eval
    )

    # Set working directory
    work_dir = os.path.join(args.log_dir, args.domain + '_' + args.task, args.algo, str(args.seed))
    print('Working directory:', work_dir)
    assert os.path.exists(work_dir), 'specified working directory does not exist'
    model_dir = utils.make_dir(os.path.join(work_dir, 'model'))
    video_dir = utils.make_dir(os.path.join(work_dir, 'video'))
    video = VideoRecorder(video_dir if args.save_video else None, height=448, width=448)

    # Check if evaluation has already been run
    results_fp = os.path.join(work_dir, args.Eval + '.pt')
    assert not os.path.exists(results_fp), f'{args.Eval} results already exist for {work_dir}'

    # Prepare agent
    assert torch.cuda.is_available(), 'must have cuda enabled'
    cropped_obs_shape = (3 * args.frame_stack, 84, 84)
    agent = make_agent(args.algo,
                       obs_shape=cropped_obs_shape,
                       act_shape=env.action_space.shape,
                       args=Args.algo)
    agent = torch.load(os.path.join(model_dir, str(args.train_steps) + '.pt'))
    agent.train(False)

    print(f'\nEvaluating {work_dir} for {args.eval_episodes} episodes (mode: {args.Eval})')
    reward = evaluate(env, agent, video, args.eval_episodes, args.Eval)
    print('Reward:', int(reward))

    adapt_reward = None
    if args.algo == 'pad':
        env = make_env(
            domain_name=args.domain,
            task_name=args.task,
            seed=args.seed + 42,
            episode_length=args.episode_length,
            action_repeat=args.action_repeat,
            mode=args.Eval
        )
        adapt_reward = evaluate(env, agent, video, args.eval_episodes, args.Eval, adapt=True)
        print('Adapt reward:', int(adapt_reward))

    # Save results
    torch.save({
        'args': args,
        'reward': reward,
        'adapt_reward': adapt_reward
    }, results_fp)
    print('Saved results to', results_fp)


if __name__ == '__main__':
    args = parse_args()
    main(args)
