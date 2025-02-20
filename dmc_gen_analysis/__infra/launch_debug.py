def torch_cuda():
    import torch
    _ = torch.cuda.is_available()
    print("cuda is available " if _ else "cuda is not available")
    a = torch.FloatTensor([10, 20]).to('cuda')
    print(a @ a.T, "is working!")


def gym_render():
    import gym
    env = gym.make('Reacher-v2')
    env.reset()
    img = env.render('rgb_array')

    print(img.shape, "is rendered")


def dmc_debug():
    from dm_control import suite
    print(suite, "is working!")


def torch_upload():
    from ml_logger import logger
    import numpy as np

    logger.configure(root_dir="http://54.71.92.65:9080", prefix="geyang/ml_logger-debug/test-1",
                     register_experiment=True)
    logger.log_params(args={})

    with logger.Sync():
        import os
        import torch
        from pycurl import Curl
        from tempfile import NamedTemporaryFile

        logger.remove('upload/example.pt')

        with NamedTemporaryFile(delete=True) as f:
            torch.save(np.ones([10_000_000]), f)
            # torch.save(np.ones([1000_000]), f)
            logger.print(f.name)

            c = Curl()
            c.setopt(c.URL, logger.root_dir)
            # proxy = os.environ.get('HTTP_PROXY')
            # c.setopt(c.PROXY, proxy)
            # logger.print('proxy:', proxy)
            c.setopt(c.TIMEOUT, 100000)
            c.setopt(c.HTTPPOST, [
                ('file', (
                    c.FORM_FILE, f.name,
                    c.FORM_FILENAME, logger.prefix + '/upload/example.pt',
                    c.FORM_CONTENTTYPE, 'plain/text',
                )),
            ])
            c.perform()
            c.close()

        logger.print('done')


        # logger.remove(".")
        # a = np.ones([1, 1, 100_000_000 // 4])
        # logger.print(f"the size of the tensor is {a.size}")
        # data = dict(key="ok", large=a)
        # logger.torch_save(data, f"save/data-{logger.now('%H.%M.%S')}.pkl")
    logger.print('done')


if __name__ == '__main__':
    import jaynes

    # jaynes.config("supercloud", launch=dict(n_gpu=0))
    jaynes.config("local", launch=dict(n_gpu=0))
    # ip = "visiongpu50"
    # ip = "improbable005"
    for ip in [
        "improbable005",
        # "improbable006",
        # "improbable007",
        # "improbable008",
        # "improbable010"
    ]:
        # jaynes.config("vision", launch=dict(ip=ip))
        # jaynes.run(dmc_debug)
        # jaynes.run(torch_cuda)
        # jaynes.run(gym_render)
        jaynes.run(torch_upload)
    jaynes.listen(200)
