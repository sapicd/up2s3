# -*- coding: utf-8 -*-
"""
    up2s3
    ~~~~~

    Save uploaded pictures in AWS S3.

    :copyright: (c) 2021 by Hiroshi.tao.
    :license: Apache 2.0, see LICENSE for more details.
"""

__version__ = "0.1.0"
__author__ = "staugur <me@tcw.im>"
__hookname__ = "up2s3"
__description__ = "将图片保存到S3"
__catalog__ = "upload"

from flask import g
from io import BytesIO
from posixpath import join
from mimetypes import guess_type
from boto3.session import Session
from boto3.exceptions import Boto3Error
from utils._compat import string_types
from utils.web import set_site_config
from utils.tool import slash_join


intpl_localhooksetting = """
<div class="layui-col-xs12 layui-col-sm12 layui-col-md6">
    <fieldset
        class="layui-elem-field layui-field-title"
        style="margin-bottom: auto"
    >
        <legend>
            AWS S3（{% if "up2s3" in g.site.upload_includes %}使用中{% else
            %}未使用{% endif %}）
        </legend>
        <div class="layui-field-box">
            <div class="layui-form-item">
                <label class="layui-form-label"
                    ><b style="color: red">*</b> Bucket</label
                >
                <div class="layui-input-block">
                    <input
                        type="text"
                        name="s3_bucket"
                        value="{{ g.site.s3_bucket }}"
                        placeholder="S3服务的存储桶名称"
                        autocomplete="off"
                        class="layui-input"
                    />
                </div>
            </div>
            <div class="layui-form-item">
                <label class="layui-form-label"
                    ><b style="color: red">*</b> AccessKey</label
                >
                <div class="layui-input-block">
                    <input
                        type="text"
                        name="s3_ak"
                        value="{{ g.site.s3_ak }}"
                        placeholder="AWS访问密钥ID"
                        autocomplete="off"
                        class="layui-input"
                    />
                </div>
            </div>
            <div class="layui-form-item">
                <label class="layui-form-label"
                    ><b style="color: red">*</b> SecretKey</label
                >
                <div class="layui-input-block">
                    <input
                        type="password"
                        name="s3_sk"
                        value="{{ g.site.s3_sk }}"
                        placeholder="AWS访问密钥密码"
                        autocomplete="off"
                        class="layui-input"
                    />
                </div>
            </div>
            <div class="layui-form-item">
                <label class="layui-form-label">自定义域名</label>
                <div class="layui-input-block">
                    <input
                        type="url"
                        name="s3_dn"
                        value="{{ g.site.s3_dn }}"
                        placeholder="S3服务绑定的自定义域名"
                        autocomplete="off"
                        class="layui-input"
                    />
                </div>
            </div>
            <div class="layui-form-item">
                <label class="layui-form-label">存储根目录</label>
                <div class="layui-input-block">
                    <input
                        type="text"
                        name="s3_basedir"
                        value="{{ g.site.s3_basedir }}"
                        placeholder="图片存储到S3的基础目录，默认是根目录"
                        autocomplete="off"
                        class="layui-input"
                    />
                </div>
            </div>
        </div>
    </fieldset>
</div>
"""


def get_session(region_name=None):
    ak = g.cfg.s3_ak
    sk = g.cfg.s3_sk
    region = g.cfg.s3_region or region_name
    return Session(
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        region_name=region,
    )


def upimg_save(**kwargs):
    res = dict(code=1)
    try:
        filename = kwargs["filename"]
        stream = kwargs["stream"]
        upload_path = kwargs.get("upload_path") or ""
        if not filename or not stream:
            return ValueError
    except (KeyError, ValueError):
        res.update(msg="Parameter error")
    else:
        bucket = g.cfg.s3_bucket
        ak = g.cfg.s3_ak
        sk = g.cfg.s3_sk
        dn = g.cfg.s3_dn
        s3_basedir = g.cfg.s3_basedir or ""
        if not bucket or not ak or not sk:
            res.update(msg="The s3 parameter error")
            return res
        errmsg = "An unknown error occurred in the program"
        if isinstance(upload_path, string_types):
            if upload_path.startswith("/"):
                upload_path = upload_path.lstrip("/")
            if s3_basedir.startswith("/"):
                s3_basedir = s3_basedir.lstrip("/")
            filepath = join(s3_basedir, upload_path, filename)
            #: 使用AWS官方SDK上传
            session = get_session()
            region = g.cfg.s3_region
            if not region:
                try:
                    info = session.client("s3").get_bucket_location(
                        Bucket=bucket,
                    )
                    if "LocationConstraint" not in info:
                        raise ValueError
                except (Boto3Error, ValueError) as e:
                    res.update(code=500, msg=str(e) or errmsg)
                    return res
                else:
                    region = info["LocationConstraint"]
                    session = get_session(region)
                    set_site_config(dict(s3_region=region))
            s3 = session.resource("s3").Bucket(bucket)
            try:
                mime_type, _ = guess_type(filename)
                s3.upload_fileobj(
                    BytesIO(stream),
                    filepath,
                    ExtraArgs=dict(ACL="public-read", ContentType=mime_type),
                )
            except Boto3Error as e:
                res.update(code=500, msg=str(e) or errmsg)
            else:
                src = "https://{}.s3.{}.amazonaws.com/{}".format(
                    bucket, region, filepath
                )
                if dn:
                    src = slash_join(dn, filepath)
                res.update(
                    code=0,
                    src=src,
                    basedir=s3_basedir,
                )
        else:
            res.update(msg="The upload_path type error")
    return res


def upimg_delete(sha, upload_path, filename, basedir, save_result):
    s3_basedir = g.cfg.s3_basedir or ""
    filepath = join(basedir or s3_basedir, upload_path, filename)
    session = get_session()
    s3 = session.resource("s3").Bucket(g.cfg.s3_bucket)
    s3.Object(filepath).delete()
