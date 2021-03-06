#!/usr/bin/env python
"""Signing script
"""
import aiohttp
import asyncio
import logging
import os
import ssl
import sys
import traceback

import scriptworker.client
from scriptworker.context import Context
from scriptworker.exceptions import ScriptWorkerTaskException
from signingscript.task import detached_sigfiles, download_files, get_token, \
    sign_file, task_cert_type, task_signing_formats, validate_task_schema
from signingscript.utils import copy_to_artifact_dir, load_json, load_signing_server_config


log = logging.getLogger(__name__)


# SigningContext {{{1
class SigningContext(Context):
    signing_servers = None

    def __init__(self):
        super(SigningContext, self).__init__()

    def write_json(self, *args):
        pass


# async_main {{{1
async def async_main(context):
    work_dir = context.config['work_dir']
    context.task = scriptworker.client.get_task(context.config)
    log.info("validating task")
    validate_task_schema(context)
    context.signing_servers = load_signing_server_config(context)
    cert_type = task_cert_type(context.task)
    signing_formats = task_signing_formats(context.task)
    # TODO scriptworker needs to validate CoT artifact
    # Use standard SSL for downloading files.
    with aiohttp.ClientSession() as base_ssl_session:
        orig_session = context.session
        context.session = base_ssl_session
        filelist = await download_files(context)
        context.session = orig_session
    log.info("getting token")
    await get_token(context, os.path.join(work_dir, 'token'), cert_type, signing_formats)
    for filename in filelist:
        log.info("signing %s", filename)
        source = os.path.join(work_dir, filename)
        await sign_file(context, source, cert_type, signing_formats,
                        context.config["ssl_cert"])
        detached_signatures = detached_sigfiles(source, signing_formats)
        copy_to_artifact_dir(context, source)
        for detached_tuple in detached_signatures:
            copy_to_artifact_dir(context, detached_tuple[1])
    log.info("Done!")


# config {{{1
def get_default_config():
    """ Create the default config to work from.
    """
    cwd = os.getcwd()
    parent_dir = os.path.dirname(cwd)
    default_config = {
        'signing_server_config': 'server_config.json',
        'tools_dir': os.path.join(parent_dir, 'build-tools'),
        'work_dir': os.path.join(parent_dir, 'work_dir'),
        'artifact_dir': os.path.join(parent_dir, '/src/signing/artifact_dir'),
        'my_ip': "127.0.0.1",
        'ssl_cert': None,
        'signtool': "signtool",
        'schema_file': os.path.join(cwd, 'signingscript', 'data', 'signing_task_schema.json'),
        'verbose': True,
    }
    return default_config


# main {{{1
def usage():
    print("Usage: {} CONFIG_FILE".format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)


def main(name=None, config_path=None):
    if name not in (None, '__main__'):
        return
    context = SigningContext()
    context.config = get_default_config()
    if config_path is None:
        if len(sys.argv) != 2:
            usage()
        config_path = sys.argv[1]
    context.config.update(load_json(path=config_path))
    if context.config.get('verbose'):
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=log_level
    )
    logging.getLogger("taskcluster").setLevel(logging.WARNING)
    loop = asyncio.get_event_loop()
    kwargs = {}
    if context.config.get('ssl_cert'):
        sslcontext = ssl.create_default_context(cafile=context.config['ssl_cert'])
        kwargs['ssl_context'] = sslcontext
    else:
        kwargs['verify_ssl'] = False
    conn = aiohttp.TCPConnector(**kwargs)
    with aiohttp.ClientSession(connector=conn) as session:
        context.session = session
        try:
            loop.run_until_complete(async_main(context))
        except ScriptWorkerTaskException as exc:
            traceback.print_exc()
            sys.exit(exc.exit_code)
    loop.close()


main(name=__name__)
