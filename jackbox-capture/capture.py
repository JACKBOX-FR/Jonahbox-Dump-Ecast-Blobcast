import base64
import json
import time
import zlib
import gzip
from pathlib import Path

from mitmproxy import http


OUTPUT_DIR = Path("captures")
OUTPUT_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "traffic.jsonl"


def ts():
    return time.time()


def connection_info(flow):
    client = None
    server = None

    if flow.client_conn:
        client = flow.client_conn.peername

    if flow.server_conn:
        server = flow.server_conn.address

    return client, server


def decompress_body(data, encoding):
    if not data:
        return data, False

    encoding = (encoding or "").lower()

    try:
        if encoding == "gzip":
            return gzip.decompress(data), True

        if encoding == "deflate":
            try:
                return zlib.decompress(data), True
            except zlib.error:
                return zlib.decompress(data, -zlib.MAX_WBITS), True

        if encoding == "br":
            try:
                import brotli
                return brotli.decompress(data), True
            except ImportError:
                return data, False
            except Exception:
                return data, False

    except Exception:
        return data, False

    return data, False


def is_text_content(content_type):
    if not content_type:
        return False

    content_type = content_type.lower()

    return (
        content_type.startswith("text/")
        or "json" in content_type
        or "javascript" in content_type
        or "xml" in content_type
        or "graphql" in content_type
        or "x-www-form-urlencoded" in content_type
        or "svg" in content_type
    )


def encode_body(data, headers):
    if not data:
        return {
            "size": 0,
            "encoding": "empty",
            "data": ""
        }

    content_encoding = headers.get("content-encoding", "")
    content_type = headers.get("content-type", "")

    decoded, decompressed = decompress_body(
        data,
        content_encoding
    )

    if is_text_content(content_type):
        try:
            text = decoded.decode("utf-8")

            return {
                "size": len(data),
                "decoded_size": len(decoded),
                "encoding": (
                    f"{content_encoding} -> utf-8"
                    if decompressed
                    else "utf-8"
                ),
                "data": text
            }

        except UnicodeDecodeError:
            pass

    return {
        "size": len(data),
        "decoded_size": len(decoded),
        "encoding": (
            f"{content_encoding} -> binary"
            if decompressed
            else "binary"
        ),
        "data_base64": base64.b64encode(decoded).decode("ascii")
    }


def save(record):
    with OUTPUT_FILE.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                record,
                ensure_ascii=False
            )
            + "\n"
        )


def request(flow: http.HTTPFlow):
    req = flow.request

    client, server = connection_info(flow)

    body = encode_body(
        req.raw_content,
        req.headers
    )

    record = {
        "timestamp": ts(),
        "type": "http_request",

        "client": client,
        "server": server,

        "host": req.host,
        "port": req.port,
        "scheme": req.scheme,

        "method": req.method,
        "url": req.url,
        "path": req.path,

        "headers": dict(req.headers),

        "body": body
    }

    save(record)


def response(flow: http.HTTPFlow):
    res = flow.response

    client, server = connection_info(flow)

    body = encode_body(
        res.raw_content,
        res.headers
    )

    record = {
        "timestamp": ts(),
        "type": "http_response",

        "client": client,
        "server": server,

        "host": flow.request.host,
        "port": flow.request.port,
        "scheme": flow.request.scheme,

        "method": flow.request.method,
        "url": flow.request.url,
        "path": flow.request.path,

        "status": res.status_code,

        "headers": dict(res.headers),

        "body": body
    }

    save(record)


def websocket_message(flow: http.HTTPFlow):
    if not flow.websocket:
        return

    if not flow.websocket.messages:
        return

    message = flow.websocket.messages[-1]

    client, server = connection_info(flow)

    content = message.content

    if isinstance(content, bytes):
        try:
            decoded = content.decode("utf-8")
            content_data = {
                "encoding": "utf-8",
                "size": len(content),
                "data": decoded
            }
        except UnicodeDecodeError:
            content_data = {
                "encoding": "binary",
                "size": len(content),
                "data_base64": base64.b64encode(content).decode("ascii")
            }
    else:
        content_data = {
            "encoding": "text",
            "size": len(str(content)),
            "data": str(content)
        }

    record = {
        "timestamp": ts(),
        "type": "websocket_message",

        "client": client,
        "server": server,

        "host": flow.request.host,
        "path": flow.request.path,

        "direction": (
            "client_to_server"
            if message.from_client
            else "server_to_client"
        ),

        "content": content_data
    }

    save(record)


def error(flow: http.HTTPFlow):
    if not flow.error:
        return

    client, server = connection_info(flow)

    record = {
        "timestamp": ts(),
        "type": "error",

        "client": client,
        "server": server,

        "host": (
            flow.request.host
            if flow.request
            else None
        ),

        "error": str(flow.error)
    }

    save(record)