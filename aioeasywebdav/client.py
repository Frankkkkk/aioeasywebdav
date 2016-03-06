import os
import ssl
import time
import asyncio
import aiohttp
import platform
from numbers import Number
import xml.etree.cElementTree as xml
from collections import namedtuple
from urllib.request import urlparse

from http.client import responses as HTTP_CODES
from urllib.parse import urlparse

DOWNLOAD_CHUNK_SIZE_BYTES = 1 * 1024 * 1024


class WebdavException(Exception):
    pass

class ConnectionFailed(WebdavException):
    pass

class WebdavProgress(object):
    STATUS_NEW = "STATUS_NEW"
    STATUS_ACTIVE = "STATUS_ACTIVE"
    STATUS_PAUSED = "STATUS_PAUSED"
    STATUS_DONE = "STATUS_DONE"
    STATUS_ERROR = "STATUS_ERROR"

    _WINDOW = 20

    def __init__(self):
        self.future = None
        self.length = None
        self.current = 0
        self.updated = time.time()

        self.enabled = asyncio.Event()
        self.enabled.set()
        self._status = self.STATUS_NEW
        self._tracking = [(0,self.updated)] * self._WINDOW

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, s):
        self.updated = time.time()
        self._status = s

    def add_length(self, size):
        now = time.time()
        self.status = self.STATUS_ACTIVE

        self.updated = now
        self.current += size

        self._tracking.append((self.current, now))
        self._tracking = self._tracking[1:self._WINDOW+1]

    @property
    def rate(self):
        sLen, sTime = self._tracking[0]
        eLen, eTime = self._tracking[-1]
        dTime = (eTime - sTime)
        return 0 if not dTime else (eLen - sLen) / dTime

    async def Pause(self):
        self.status = self.STATUS_PAUSED
        self.enabled.clear()

    async def Resume(self):
        self.enabled.set()

    @property
    async def Paused(self):
        return not self.enabled.is_set()

def codestr(code):
    return HTTP_CODES.get(code, 'UNKNOWN')


File = namedtuple('File', ['name', 'size', 'mtime', 'ctime', 'contenttype'])


def prop(elem, name, default=None):
    child = elem.find('.//{DAV:}' + name)
    return default if child is None else child.text


def elem2file(elem, basepath=''):
    return File(
        prop(elem, 'href').replace(basepath, ''),
        int(prop(elem, 'getcontentlength', 0)),
        prop(elem, 'getlastmodified', ''),
        prop(elem, 'creationdate', ''),
        prop(elem, 'getcontenttype', ''),
    )


class OperationFailed(WebdavException):
    _OPERATIONS = dict(
        HEAD = "get header",
        GET = "download",
        PUT = "upload",
        DELETE = "delete",
        MKCOL = "create directory",
        PROPFIND = "list directory",
        )

    def __init__(self, method, path, expected_code, actual_code):
        self.method = method
        self.path = path
        self.expected_code = expected_code
        self.actual_code = actual_code
        operation_name = self._OPERATIONS[method]
        self.reason = 'Failed to {operation_name} "{path}"'.format(**locals())
        expected_codes = (expected_code,) if isinstance(expected_code, Number) else expected_code
        expected_codes_str = ", ".join('{0} {1}'.format(code, codestr(code)) for code in expected_codes)
        actual_code_str = codestr(actual_code)
        msg = '''\
{self.reason}.
  Operation     :  {method} {path}
  Expected code :  {expected_codes_str}
  Actual code   :  {actual_code} {actual_code_str}'''.format(**locals())
        super(OperationFailed, self).__init__(msg)

class Client(object):
    def __init__(self, url=None, host=None, port=0, auth=None, username=None, password=None,
                 protocol='http', verify_ssl=True, path=None, cert=None):
        self.basepath = ''
        if url:
            self.baseurl = url
            self.basepath = urlparse(url).path
        else:
            if not port:
                port = 443 if protocol == 'https' else 80
            self.baseurl = '{0}://{1}:{2}'.format(protocol, host, port)
            if path:
                self.baseurl = '{0}/{1}'.format(self.baseurl, path)
                self.basepath = path
        self.cwd = '/'

        sslcontext = None
        if cert:
            self.session.cert = cert

            sslcontext = ssl.create_default_context(cafile=cert)
        conn = aiohttp.TCPConnector(ssl_context=sslcontext, verify_ssl=verify_ssl)

        if not auth and username and password:
            auth = aiohttp.BasicAuth(username, password=password)

        self.session = aiohttp.ClientSession(connector=conn, auth=auth)

        # self.session.stream = True

    async def _send(self, method, path, expected_code, **kwargs):
        url = self._get_url(path)
        response = await self.session.request(method, url, allow_redirects=False, **kwargs)
        if isinstance(expected_code, Number) and response.status != expected_code \
            or not isinstance(expected_code, Number) and response.status not in expected_code:
            raise OperationFailed(method, path, expected_code, response.status)
        return response

    def _get_url(self, path):
        path = str(path).strip()
        if path.startswith('/'):
            return self.baseurl + path
        return "".join((self.baseurl, self.cwd, path))

    def cd(self, path):
        path = path.strip()
        if not path:
            return
        stripped_path = '/'.join(part for part in path.split('/') if part) + '/'
        if stripped_path == '/':
            self.cwd = stripped_path
        elif path.startswith('/'):
            self.cwd = '/' + stripped_path
        else:
            self.cwd += stripped_path

    async def mkdir(self, path, safe=False):
        expected_codes = 201 if not safe else (201, 301, 405)
        response = await self._send('MKCOL', path, expected_codes)
        await response.release()

    def mkdirs(self, path):
        dirs = [d for d in path.split('/') if d]
        if not dirs:
            return
        if path.startswith('/'):
            dirs[0] = '/' + dirs[0]
        old_cwd = self.cwd
        try:
            for dir in dirs:
                try:
                    self.mkdir(dir, safe=True)
                except Exception as e:
                    if e.actual_code == 409:
                        raise
                finally:
                    self.cd(dir)
        finally:
            self.cd(old_cwd)

    async def rmdir(self, path, safe=False):
        path = str(path).rstrip('/') + '/'
        expected_codes = 204 if not safe else (204, 404)
        response = await self._send('DELETE', path, expected_codes)
        await response.release()

    async def delete(self, path):
        response = await self._send('DELETE', path, 204)
        await response.release()

    def upload(self, local_path_or_fileobj, remote_path):
        if isinstance(local_path_or_fileobj, str):
            with open(local_path_or_fileobj, 'rb') as f:
                self._upload(f, remote_path)
        else:
            self._upload(local_path_or_fileobj, remote_path)


    async def background_upload(self, local_path, remote_path):
        """
        :param str local_path: where to upload file from
        :param str remote_path: remote file to store to
        :return: WebdavProgress
        """
        progress = WebdavProgress()
        progress.length = os.path.getsize(local_path)

        def chunk(fh):
            for dat in fh.read(DOWNLOAD_CHUNK_SIZE_BYTES):
                progress.add_length(len(dat))
                yield dat

        with open(local_path, 'rb') as f:
            cor = self._upload(chunk(f), remote_path)

        progress.future = asyncio.ensure_future(cor)
        return progress

    async def _upload(self, fileobj, remote_path, **kwargs):
        response = await self._send('PUT', remote_path, (200, 201, 204), data=fileobj, **kwargs)
        await response.release()


    async def download(self, remote_path, local_path_or_fileobj):
        response = await self._send('GET', remote_path, 200, chunked=True)
        if isinstance(local_path_or_fileobj, str):
            with open(local_path_or_fileobj, 'wb') as f:
                await self._download(f, response)
        else:
            await self._download(local_path_or_fileobj, response)
        await response.release()

    async def background_download(self, remote_file, local_path_or_fileobj, done_callback=None):
        """
        :param File remote_file: File object from ls()
        :param (str or file) local_path_or_fileobj: where to download file to
        :return: WebdavProgress
        """
        progress = WebdavProgress()
        progress.length = remote_file.size

        response = await self._send('GET', remote_file.name, 200, chunked=True)
        if isinstance(local_path_or_fileobj, str):
            fileobj = open(local_path_or_fileobj, 'wb')
            def cb(success):
                fileobj.close()
                progress.status = progress.STATUS_DONE if success else progress.STATUS_ERROR
                if done_callback:
                    done_callback(success)
        else:
            fileobj = local_path_or_fileobj
            def cb(success):
                progress.status = progress.STATUS_DONE if success else progress.STATUS_ERROR
                if done_callback:
                    done_callback(success)

        cor = self._download(fileobj, response, progress.length, progress.add_length, cb, progress.enabled)

        progress.length = remote_file.size
        progress.future = asyncio.ensure_future(cor)
        return progress

    @staticmethod
    async def _download(fileobj, response, expected_length = 0, progress_callback = None, done_callback=None, enabled_event = None):
        """
        :param file fileobj: file handle open for write
        :param aoihttp.ClientResponse response: open get response (chunked)
        :param (function or None) progress_callback: optional callback which gets notified of length of each chunk
        :param (function or None) done_callback: optional callback called when finished with boolean of success
        :param (asyncio.Event or None) enabled_event: optional Event used to pause/resume download
        :return:
        """
        success = False
        try:
            length = 0
            while not enabled_event or (await enabled_event.wait()):
                chunk = await response.content.read(DOWNLOAD_CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                fileobj.write(chunk)
                length += len(chunk)
                if progress_callback:
                    progress_callback(len(chunk))
            if not expected_length or length == expected_length:
                success = True
        finally:
            await response.release()
            if done_callback:
                done_callback(success)

    async def ls(self, remote_path=''):
        """
        :param str remote_path: path relative to the server to list
        :return: [File]
        """
        headers = {'Depth': '1'}
        response = await self._send('PROPFIND', remote_path, (207, 301), headers=headers)

        # Redirect
        if response.status == 301:
            url = urlparse(response.headers['location'])
            return self.ls(url.path)

        tree = xml.fromstring(await response.read())
        await response.release()
        return [elem2file(elem, self.basepath) for elem in tree.findall('{DAV:}response')]

    async def exists(self, remote_path):
        response = await self._send('HEAD', remote_path, (200, 301, 404))
        ret =  True if response.status != 404 else False
        await response.release()
        return ret
