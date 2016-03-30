aioEasyWebDAV: A WebDAV Client for Python 3.5 asyncio
=====================================================

This is am aiohttp port of the requests-based EasyWebDAV ( http://github.com/amnong/easywebdav ).


Features
--------

* Basic authentication
* Creating directories, removing directories and files
* Uploading and downloading files
* Directory listing
* Support for client side SSL certificates

Installation
------------

Install using distribute:

    pip install aioeasywebdav

Quick Start
-----------

    import aioeasywebdav
    loop = asyncio.get_event_loop()
    
    # Start off by creating a client object. Username and
    # password may be omitted if no authentication is needed.
    webdav = aioeasywebdav.connect('webdav.your-domain.com', username='myuser', password='mypass')
    
    # Do some stuff:
    loop.run_until_complete(webdav.mkdir('some_dir'))
    loop.run_until_complete(webdav.rmdir('another_dir'))
    
    async def fn():
        await webdav.download('/remote/path/to/file', '/local/target/file')
        await webdav.upload('/local/path/to/file', '/remote/target/file')
    loop.run_until_complete(fn())

Client object API
-----------------

The API is pretty much self-explanatory:

    cd(path)
    ls(path=None)
    exists(remote_path)
    mkdir(path, safe=False)
    mkdirs(path)
    rmdir(path, safe=False)
    delete(file_path)
    upload(local_path_or_fileobj, remote_path)
    download(remote_path, local_path)

Using clientside SSL certificate
--------------------------------

    webdav = aioeasywebdav.connect('secure.example.net',
                                username='user',
                                password='pass',
                                protocol='https',
                                cert="/path/to/your/certificate.pem")
    # Do some stuff:
    print(await webdav.ls())

Please note that all options and restriction regarding the "cert" parameter from
[Requests API](http://docs.python-requests.org/en/latest/api/) apply here as the parameter is only passed through!

Developing aioEasyWebDAV
---------------------

Working with a virtual environment is highly recommended:

    virtualenv --no-site-packages aioeasywebdav_dev
    source aioeasywebdav_dev/bin/activate

Installing the library in development-mode:

    EASYWEBDAV_DEV=1 python setup.py develop

The first part of the command causes setup.py to install development dependencies, in addition to the normal dependencies.

Running the tests:

    nosetests --with-yanc --nologcapture --nocapture tests

Running the tests with WebDAV server logs:

    WEBDAV_LOGS=1 nosetests --with-yanc --nologcapture --nocapture -v tests
