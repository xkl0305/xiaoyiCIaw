import argparse
import json
import os
import shutil
import uuid
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import logging
import requests
import sys
import zipfile
import time
import tempfile
import re

zip_input_files_url = "https://h5hosting-drcn.dbankcdn.cn/cch5/HAG/D1E0CiDwLKSTla6LZEqEHDzqA/import.json"
XIAO_YI_ENV_PATH = "/home/sandbox/.openclaw/.xiaoyienv"
PARENT_FOLDER_NAME = "小艺Claw"
DRIVE_URL_PATH = "/drive/v1/files"
QUERY_ROOT_PARAM = "&queryParam=recycled=false%20and%20parentFolder='root'%20and%20"
QUERY_FILE_FIELDS = "files(id,mimeType,fileName,size,editedTime)"
MAX_TIMEOUT = 30
QUERY_ERROR = "查询异常"
QUERY_FAIL = "查询失败"
FOLDER_NOT_EXIST = "小艺Claw目录不存在"
FILE_NOT_EXIST = "文件不存在"

global_support_sidecar = False


# 日志文件路径
LOG_DIR = os.path.join(tempfile.gettempdir(), "logs")
print("log:", LOG_DIR)
LOG_FILE = os.path.join(LOG_DIR, f"{os.path.basename(__file__).replace('.py', '')}.log")


# 创建日志目录并设置权限
os.makedirs(LOG_DIR, mode=0o700, exist_ok=True)

# 创建日志文件并设置权限（如果不存在）
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w') as f1:
        pass
    os.chmod(LOG_FILE, 0o600)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


# Token 过期错误提示
TOKEN_EXPIRED_MESSAGE = {
    "status": "error",
    "error_code": "TOKEN_EXPIRED",
    "message": "授权已失效，请退出小艺Claw，再次启动小艺Claw重新获取授权后重试。"
}


def check_token_expired(response):
    """
    检查响应是否表示 token 过期
    :param response: HTTP 响应对象
    :return: True 如果 token 过期，否则 False
    """
    if response.status_code == 401:
        return True
    # 有些接口可能返回 403 或其他状态码表示授权问题
    if response.status_code == 403:
        try:
            result = response.json()
            # 检查是否是授权相关的错误
            if 'code' in result and result.get('code') in [401, 403, 'Unauthorized', 'Forbidden']:
                return True
        except:
            pass
    return False


def print_token_expired():
    """打印 token 过期的友好提示"""
    print(json.dumps(TOKEN_EXPIRED_MESSAGE, ensure_ascii=False))


class UploadFileHwDrive(object):
    def __init__(self, auth):
        self.trace_id = str(uuid.uuid4())[:16]
        self.auth = f"Bearer {auth}"

    def about_get(self):
        """
        调用 /drive/v1/about 接口云空间用户相关信息
        :return: 用户相关信息
        """
        base_url = get_base_url()
        url = f"{base_url}/drive/v1/about?fields=*"
        headers = {
            "Authorization": self.auth
        }
        try:
            response = requests.get(url, headers=headers, timeout=MAX_TIMEOUT)
            if check_token_expired(response):
                logger.error("Token expired in about_get")
                return {"error": "TOKEN_EXPIRED"}
            if response.status_code == 200:
                result = response.json()
                return result
            else:
                logger.error(f"Response: {response.text}")
        except Exception as e:
            logger.error(f"Error: An error occurred while creating directory: {e}")
            return None


    def get_celiaclaw_file_id(self):
        base_url = get_base_url()
        url = f"{base_url}{DRIVE_URL_PATH}?fields=files(id){QUERY_ROOT_PARAM}fileName='{PARENT_FOLDER_NAME}'"
        headers = {
            "Authorization": self.auth
        }
        try:
            response = requests.get(url, headers=headers, timeout=MAX_TIMEOUT)
            if check_token_expired(response):
                logger.error("Token expired in get_celiaclaw_file_id")
                return "TOKEN_EXPIRED"
            if response.status_code == 200:
                result = response.json()
                if result["files"]:
                    file_id = result["files"][0]["id"]
                    return file_id
                else:
                    return ""
            else:
                logger.error(f"Response: {response.text}")
                return ""
        except Exception as e:
            logger.error(f"Error: An error occurred while creating directory: {e}")
            return ""


    def get_file_list(self, folder_id):
        """
        查询云盘指定路径下的所有文件列表（支持分页）
        :param folder_id: 云盘路径ID（父文件夹ID）
        :return: 文件列表JSON数据，失败返回None
        """
        base_url = get_base_url()
        all_files = []
        next_cursor = None
        page_count = 0
        
        while True:
            page_count += 1
            # 构建URL，包含分页参数
            url = f"{base_url}{DRIVE_URL_PATH}?fields={QUERY_FILE_FIELDS},nextCursor&queryParam=parentFolder='{folder_id}'&pageSize=100"
            if next_cursor:
                url += f"&cursor={next_cursor}"
            
            headers = {
                "Authorization": self.auth
            }
            logger.info(f"get_file_list page {page_count}, url: {url}")
            
            try:
                response = requests.get(url, headers=headers, timeout=MAX_TIMEOUT)
                if response.status_code == 200:
                    result = response.json()
                    # 获取当前页的文件列表
                    files = result.get('files', [])
                    all_files.extend(files)
                    logger.info(f"get_file_list page {page_count}, files count: {len(files)}")
                    
                    # 检查是否还有下一页
                    next_cursor = result.get('nextCursor')
                    if not next_cursor:
                        # 没有更多数据，退出循环
                        break
                else:
                    logger.error(f"Response: {response.text}")
                    return f"{QUERY_FAIL},{response.text}"
            except Exception as e:
                logger.error(f"Error: An error occurred while getting file list: {e}")
                return f"{QUERY_ERROR},e"
        
        logger.info(f" total files count: {len(all_files)}")
        return all_files

    def get_space_detail(self):
        result = self.about_get()
        if result is None:
            logger.error(f"get cloud drive space failed")
            return 0
        if result == {"error": "TOKEN_EXPIRED"}:
            return "TOKEN_EXPIRED"
        print(f"总空间：{result["storageQuota"]["userCapacity"]}")
        print(f"已用空间：{result["storageQuota"]["usedSpace"]}")
        available_space = max(0, int(result["storageQuota"]["userCapacity"]) - int(result["storageQuota"]["usedSpace"]))
        print(f"可用空间：{available_space}")
        if result["storageQuota"]["userCapacity"] == 0:
            print("您当前为基础服务用户，不支持上传文件")
        elif available_space == 0:
            print("云空间可用容量不足，建议尽快升级云空间")
        self.with_space_be_full(int(result["storageQuota"]["userCapacity"]), available_space)
        return result

    def with_space_be_full(self, total_sapce, available_space):
        if available_space < total_sapce * 0.2:
            print("云空间可用空间将满")
            return True
        else:
            return False

    def get_clouddrive_available_space(self):
        result = self.about_get()
        if result is None:
            logger.error(f"get cloud drive space failed")
            return 0
        if result == {"error": "TOKEN_EXPIRED"}:
            return "TOKEN_EXPIRED"
        available_space = max(0, int(result["storageQuota"]["userCapacity"]) - int(result["storageQuota"]["usedSpace"]))
        print(f"可用空间{available_space}")
        return available_space

    def check_space(self, file_size):
        available_space = self.get_clouddrive_available_space()
        if available_space == "TOKEN_EXPIRED":
            return "TOKEN_EXPIRED"
        if available_space < file_size:
            logger.error(f"file size {file_size} is less than available space {available_space}")
            return False
        else:
            return True

    def check_file_exists_recursive(self, file_name, folder_id):
        """
        递归查询云盘小艺Claw文件夹下是否存在指定文件名的文件或文件夹
        :param file_name: 文件名
        :param folder_id: 文件夹ID
        :return: 存在返回True，不存在返回False
        """
        result = {
            "status": "error"
        }
        ret = self.check_file_exists(file_name,folder_id)
        if ret is not None:
            result["status"] = "success"
            result["result"] = f"{file_name} exist"
            result["file"] = ret
            return result
        base_url = get_base_url()
        all_files = []
        next_cursor = None
        page_count = 0

        while True:
            page_count += 1
            url = f"{base_url}{DRIVE_URL_PATH}?fields=files(id,fileName,mimeType,size,editedTime),nextCursor&queryParam=parentFolder='{folder_id}'&pageSize=100"
            if next_cursor:
                url += f"&cursor={next_cursor}"

            headers = {
                "Authorization": self.auth
            }
            logger.info(f"get_file_list_recursive page {page_count}, url: {url}")

            try:
                response = requests.get(url, headers=headers, timeout=MAX_TIMEOUT)
                if check_token_expired(response):
                    result["status"] = "error"
                    result["error_code"] = "TOKEN_EXPIRED"
                    result["message"] = "授权已失效，请退出小艺Claw，再次启动小艺Claw重新获取授权后重试。"
                    return result

                if response.status_code == 200:
                    data = response.json()
                    files = data.get('files', [])
                    all_files.extend(files)
                    logger.info(f"get_file_list_recursive page {page_count}, files count: {len(files)}")

                    next_cursor = data.get('nextCursor')
                    if not next_cursor:
                        break
                else:
                    logger.error(f"Response: {response.text}")
                    result["status"] = "error"
                    result["error_code"] = "QUERY_FAILED"
                    result["message"] = f"查询失败: {response.text}"
                    return result
            except Exception as e:
                logger.error(f"Error in get_file_list_recursive: {e}")
                result["status"] = "error"
                result["error_code"] = "QUERY_ERROR"
                result["message"] = f"查询异常: {str(e)}"
                return result

        # 递归处理子文件夹
        for file_info in all_files:
            is_folder = file_info.get("mimeType") == "application/vnd.huawei-apps.folder"
            file_info["is_folder"] = is_folder

            # 如果是文件夹，递归获取其内容
            if is_folder:
                current_folder_id = file_info["id"]
                result = self.check_file_exists_recursive(file_name, current_folder_id)
                if result["status"] == "success":
                    return result

        logger.info(f"{file_name} does not exist in {folder_id}")
        result["result"] = f"{file_name} does not exist"
        return result

    def check_file_exists(self, file_name, folder_id):
        """
        检查云盘中是否存在指定文件名的文件
        :param file_name: 文件名
        :param folder_id: 文件夹ID
        :return: 存在返回True，不存在返回False
        """
        base_url = get_base_url()
        query_param = f"&queryParam=recycled=false%20and%20parentFolder='{folder_id}'%20and%20"
        url = f"{base_url}{DRIVE_URL_PATH}?fields={QUERY_FILE_FIELDS}{query_param}fileName='{file_name}'"
        headers = {
            "Authorization": self.auth
        }
        try:
            response = requests.get(url, headers=headers, timeout=MAX_TIMEOUT)
            if check_token_expired(response):
                logger.error("Token expired in check_file_exists")
                return None
            if response.status_code == 200:
                result = response.json()
                if result.get("files"):
                    logger.info(f"the file {file_name} exists in {folder_id}")
                    return result.get("files")
                else:
                    logger.info(f"the file {file_name} does not exists in {folder_id}")
                    return None
            else:
                logger.error(f"Response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error: An error occurred while checking folder exists: {e}")
            return None

    def check_folder_exists(self, folder_name):
        """
        检查云盘根目录下是否存在指定名称的文件夹
        :param folder_name: 文件夹名称
        :return: 存在返回True，不存在返回False
        """
        base_url = get_base_url()
        url = f"{base_url}{DRIVE_URL_PATH}?fields=files(id){QUERY_ROOT_PARAM}fileName='{folder_name}'"
        headers = {
            "Authorization": self.auth
        }
        try:
            response = requests.get(url, headers=headers, timeout=MAX_TIMEOUT)
            if check_token_expired(response):
                logger.error("Token expired in check_folder_exists")
                return "TOKEN_EXPIRED"
            if response.status_code == 200:
                result = response.json()
                if result.get("files"):
                    logger.info(f"the folder {folder_name} exists in the cloud drive")
                    return "小艺Claw目录存在"
                else:
                    logger.info(f"the folder {folder_name} does not exists in cloud drive")
                    return "小艺Claw目录不存在"
            else:
                logger.error(f"Response: {response.text}")
                return f"{QUERY_FAIL}, {response.text}"
        except Exception as e:
            logger.error(f"Error: An error occurred while checking folder exists: {e}")
            return f"{QUERY_ERROR}, {e}"

    # 创建云空间目录
    def create_file_dir(self, dir_name, parent_folder_id):
        """
        调用 /drive/v1/files 接口创建文件夹
        :return: 创建的文件夹信息
        """
        cloud_namespace_base_url = get_base_url()
        url = f"{cloud_namespace_base_url}{DRIVE_URL_PATH}?fields=id,fileName&autoRename=false"
        data = {
            "parentFolder": [parent_folder_id],
            "fileName": dir_name,
            "mimeType": "application/vnd.huawei-apps.folder"
        }
        create_trace_id = f"{self.trace_id}_create"
        headers = {
            "Authorization": self.auth
        }
        logger.info("create dir trace_id: {}".format(create_trace_id))

        try:
            response = requests.post(url, headers=headers, json=data, verify=True, timeout=MAX_TIMEOUT)
            if check_token_expired(response):
                logger.error("Token expired in create_file_dir")
                return "TOKEN_EXPIRED"
            if response.status_code == 200:
                result = response.json()
                return result
            else:
                logger.error(f"Error: Failed to create directory, status code: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error: An error occurred while creating directory: {e}")
            print(e)
            return None

    def query_file(self, file_name, parent_folder_id):
        base_url = get_base_url()
        query_file_params = \
            f"&queryParam=recycled=false%20and%20parentFolder='{parent_folder_id}'%20and%20fileName='{file_name}'"
        url = f"{base_url}{DRIVE_URL_PATH}?fields=files(id){query_file_params}"
        headers = {
            "Authorization": self.auth
        }
        try:
            response = requests.get(url, headers=headers, timeout=MAX_TIMEOUT)
            if check_token_expired(response):
                logger.error("Token expired in query_file")
                return "TOKEN_EXPIRED"
            if response.status_code == 200:
                result = response.json()
                if result["files"]:
                    file_id = result["files"][0]["id"]
                    return file_id
                else:
                    return ""
            else:
                print(f"Response: {response.text}")
                return ""
        except Exception as e:
            logger.error(f"Error: An error occurred while creating directory: {e}")
            print(e)
            return ""


    def create_file_content(self, file_name, content):
        cloud_namespace_base_url = get_base_url()
        url = f"{cloud_namespace_base_url}/upload/drive/v1/files?uploadType=content&fields=*"
        headers = {
            "Authorization": self.auth,
            "x-hw-properties": f"filename={file_name}"
        }

        try:
            response = requests.post(url, headers=headers, data=content, verify=True, timeout=MAX_TIMEOUT)
            if response.status_code == 200:
                result = response.json()
                return result
            else:
                logger.error(f"Error: Failed to create file, status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error: An error occurred while creating file: {e}")
            print(e)
            return None

    # 创建云空间文件
    def create_file_resume(self, file_name, file_id, file_size):
        cloud_namespace_base_url = get_base_url()
        url = f"{cloud_namespace_base_url}/upload/drive/v1/files?uploadType=resume&fields=*"
        data = {
            "parentFolder": [file_id],
            "fileName": file_name
        }
        create_trace_id = f"{self.trace_id}_create_resume"
        headers = {
            "Authorization": self.auth,
            "X-Upload-Content-Length": file_size,
            "x-hw-trace-id": create_trace_id,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        logger.info("create trace_id: {}".format(create_trace_id))

        try:
            response = requests.post(url, headers=headers, json=data, verify=True, timeout=MAX_TIMEOUT)
            if response.status_code == 200:
                result = response.json()
                headers = response.headers
                resultHeader = response.headers.get("Location")
                result["uploadUrl"] = resultHeader
                return result
            else:
                logger.error(f"Error: Failed to create resume, status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error: An error occurred while creating resume: {e}")
            print(e)
            return None


    def update_file_resume(self, file_name, file_id, file_size, parent_folder_id):
        cloud_namespace_base_url = get_base_url()
        url = f"{cloud_namespace_base_url}/upload/drive/v1/files/{file_id}?uploadType=resume&fields=*"
        data = {
            "fileName": file_name,
            "parentFolder": [parent_folder_id],
        }
        create_trace_id = f"{self.trace_id}_create_resume"
        headers = {
            "Authorization": self.auth,
            "X-Upload-Content-Length": file_size,
            "x-hw-trace-id": create_trace_id,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        try:
            response = requests.patch(url, headers=headers, json=data, verify=True, timeout=MAX_TIMEOUT)
            if response.status_code == 200:
                result = response.json()
                headers = response.headers
                resultHeader = response.headers.get("Location")
                result["uploadUrl"] = resultHeader
                return result
            else:
                logger.error(f"Error: Failed to create resume, status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error: An error occurred while creating resume: {e}")
            print(e)
            return None


    def upload_file_in_chunks(self, server_id, upload_id, file_path, chunk_size=67108864):
        """
        循环上传 ZIP 文件，每次上传固定大小的块
        :param server_id: 服务器 ID
        :param upload_id: 上传 ID
        :param file_path: 文件路径
        :param chunk_size: 每次上传的字节数（默认 64MB）
        :return: 上传结果
        """
        if not os.path.exists(file_path):
            logger.info("文件不存在")
            return None

        file_size = os.path.getsize(file_path)
        logger.info(f"文件大小: {file_size} 字节")
        cloud_namespace_base_url = get_base_url()
        upload_trace_id = f"{self.trace_id}_upload"
        start_byte = 0

        while start_byte < file_size:
            end_byte = min(start_byte + chunk_size - 1, file_size - 1)
            content_range = f"bytes {start_byte}-{end_byte}/{file_size}"
            logger.info(f"上传范围: {content_range}")

            # 分块读取文件内容，避免一次性加载大文件到内存
            with open(file_path, "rb") as f:
                f.seek(start_byte)
                chunk_data = f.read(end_byte - start_byte + 1)

            url = f"{cloud_namespace_base_url}/upload/drive/v1/{server_id}/files"
            request_url = f"{url}?fields=*&uploadType=resume&uploadId={upload_id}"

            headers = {
                "Authorization": self.auth,
                "Content-Type": "application/json;charset=UTF-8",
                "Content-Range": content_range,
                "x-hw-trace-id": upload_trace_id,
            }
            try:
                response = requests.put(
                    request_url,
                    headers=headers,
                    data=chunk_data,
                    verify=True,
                    timeout=MAX_TIMEOUT
                )
                if response.status_code == 308:
                    start_byte = end_byte + 1
                    continue
                if response.status_code == 200:
                    logger.info("上传成功")
                else:
                    logger.error(f"响应内容: {response.text}")
                    return None
            except Exception as e:
                logger.error(f"请求异常: {e}")
                return None

        # 文件上传完成后，调用一次接口，不传Content-Range，传Content-Length为0
        final_url = f"{cloud_namespace_base_url}/upload/drive/v1/{server_id}/files"
        final_request_url = f"{final_url}?fields=*&uploadType=resume&uploadId={upload_id}"
        final_headers = {
            "Authorization": self.auth,
            "Content-Type": "application/json;charset=UTF-8",
            "Content-Length": "0"
        }
        max_retries = 10
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = requests.put(
                    final_request_url,
                    headers=final_headers,
                    data=b"",
                    verify=True,
                    timeout=MAX_TIMEOUT
                )
                if response.status_code == 200:
                    response_text = response.text
                    response_json = json.loads(response_text)
                    logger.info(f"上传完成接口调用成功，返回的文件ID : {str(response_json.get('id'))}")
                    return response_json.get("id")
                elif response.status_code == 308:
                    retry_count += 1
                    logger.info(f"上传完成接口返回308，等待2秒后重试（第{retry_count}次）")
                    time.sleep(2)
                    continue
                else:
                    logger.error(f"上传完成接口调用失败，状态码: {response.status_code}")
                    logger.error(f"响应内容: {response.text}")
                    return None
            except Exception as e:
                logger.info(f"上传完成接口调用异常: {e}")
                return None

        logger.error(f"上传完成接口重试{max_retries}次后仍返回308，放弃")
        return None

    def get_file_metadata(self, file_id):
        """
        获取文件元数据，包括下载链接
        :param file_id: 云盘文件ID
        :return: 文件元数据JSON，包含contentDownloadLink字段，或"TOKEN_EXPIRED"或None
        """
        base_url = get_base_url()
        url = f"{base_url}{DRIVE_URL_PATH}/{file_id}?fields=*"
        headers = {
            "Authorization": self.auth
        }
        try:
            response = requests.get(url, headers=headers, timeout=MAX_TIMEOUT)
            if check_token_expired(response):
                logger.error("Token expired in get_file_metadata")
                return "TOKEN_EXPIRED"
            if response.status_code == 200:
                result = response.json()
                logger.info(f"get_file_metadata success, file_id: {file_id}")
                return result
            else:
                logger.error(f"get_file_metadata failed: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error in get_file_metadata: {e}")
            return None

    def download_file(self, file_id, download_path):
        """
        下载云盘文件
        :param file_id: 云盘文件ID
        :param download_path: 本地下载路径
        :return: 下载结果字典
        """
        result = {
            "status": "success",
            "file_id": file_id,
            "download_path": download_path
        }
        
        # 获取文件元数据，获取下载链接
        metadata = self.get_file_metadata(file_id)
        if metadata == "TOKEN_EXPIRED":
            result["status"] = "error"
            result["error_code"] = "TOKEN_EXPIRED"
            result["message"] = "授权已失效，请退出小艺Claw，再次启动小艺Claw重新获取授权后重试。"
            return result
        
        if not metadata:
            result["status"] = "error"
            result["error_code"] = "GET_METADATA_FAILED"
            result["message"] = "获取文件元数据失败"
            return result
        
        # 获取下载链接
        download_link = metadata.get("contentDownloadLink")
        file_size = metadata.get("size")
        if not download_link:
            result["status"] = "error"
            result["error_code"] = "NO_DOWNLOAD_LINK"
            result["message"] = "文件下载链接不存在"
            return result
        
        try:
            start_byte = 0
            chunk_size = 4 * 1024 * 1024
            logger.info(f"开始下载文件，URL: {download_link}")
            while start_byte < file_size:
                end_byte = min(file_size-1, start_byte + chunk_size - 1)
                range = "bytes={}-{}".format(start_byte, end_byte)
                print(f"range:%{range}")
                headers = {
                    "Authorization": self.auth,
                    "Range": range,
                }
                response = requests.get(download_link, headers=headers, stream=True, timeout=MAX_TIMEOUT)
                response.raise_for_status()
                # 确保目标目录存在
                os.makedirs(os.path.dirname(download_path) if os.path.dirname(download_path) else ".", exist_ok=True)
                # 保存文件
                with open(download_path, 'ab+') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                start_byte = end_byte + 1
                print(f"start_byte:{start_byte}")
            f.close()
            logger.info(f"文件下载成功: {download_path}")
            result["message"] = "文件下载成功"
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"下载文件失败: {e}")
            result["status"] = "error"
            result["error_code"] = "DOWNLOAD_FAILED"
            result["message"] = f"下载文件失败: {str(e)}"
            return result
        except IOError as e:
            logger.error(f"保存文件失败: {e}")
            result["status"] = "error"
            result["error_code"] = "SAVE_FILE_FAILED"
            result["message"] = f"保存文件失败: {str(e)}"
            return result

    def rename_file(self, file_id, new_file_name):
        """
        重命名云盘文件
        :param file_id: 云盘文件ID
        :param new_file_name: 新文件名
        :return: 重命名结果字典
        """
        result = {
            "status": "success",
            "file_id": file_id,
            "new_file_name": new_file_name
        }
        
        base_url = get_base_url()
        url = f"{base_url}{DRIVE_URL_PATH}/{file_id}?fields=id,fileName,parentFolder,mimeType"
        headers = {
            "Authorization": self.auth,
            "Content-Type": "application/json"
        }
        data = {
            "fileName": new_file_name
        }
        
        try:
            response = requests.patch(url, headers=headers, json=data, timeout=MAX_TIMEOUT)
            if check_token_expired(response):
                result["status"] = "error"
                result["error_code"] = "TOKEN_EXPIRED"
                result["message"] = "授权已失效，请退出小艺Claw，再次启动小艺Claw重新获取授权后重试。"
                return result
            
            if response.status_code == 200:
                logger.info(f"文件重命名成功，file_id: {file_id}, new_name: {new_file_name}")
                result["message"] = "文件重命名成功"
                return result
            else:
                logger.error(f"文件重命名失败: {response.text}")
                result["status"] = "error"
                result["error_code"] = "RENAME_FAILED"
                result["message"] = f"重命名失败: {response.text}"
                return result
        except Exception as e:
            logger.error(f"重命名文件异常: {e}")
            result["status"] = "error"
            result["error_code"] = "RENAME_EXCEPTION"
            result["message"] = f"重命名异常: {str(e)}"
            return result

    def move_file(self, file_id, source_parent_id, destination_parent_id):
        """
        移动文件到指定文件
        :param file_id: 云文件ID
        :param source_parent_id: 原父目录ID
        :param destination_parent_id 目标父目录ID
        :return: 移动结果字典
        """
        result = {
            "status": "error",
            "file_id": file_id,
            "destination_parent_id": destination_parent_id
        }
        
        base_url = get_base_url()
        url = f"{base_url}{DRIVE_URL_PATH}/{file_id}?fields=id,fileName,parentFolder&addParentFolder={destination_parent_id}&removeParentFolder={source_parent_id}"
        headers = {
            "Authorization": self.auth,
            "Content-Type": "application/json"
        }
        data = {
            "parentFolder": [destination_parent_id]
        }
        
        try:
            response = requests.patch(url, headers=headers, json=data, timeout=MAX_TIMEOUT)
            if check_token_expired(response):
                result["status"] = "error"
                result["error_code"] = "TOKEN_EXPIRED"
                result["message"] = "授权已失效，请退出小艺Claw，再次启动小艺Claw重新获取授权后重试。"
                return result
            
            if response.status_code == 200:
                file_info = response.json()
                new_parent_id = file_info["parentFolder"]
                if new_parent_id[0] == destination_parent_id :
                    logger.info(f"文件移动成功，file_id: {file_id}, destination_parent_id: {destination_parent_id}")
                    result["status"] = "success"
                    result["message"] = "文件移动成功"
                else:
                    logger.info(f"文件移动错误，file_id: {file_id}, destination_parent_id: {destination_parent_id}")
                    result["message"] = "文件移动错误"
                return result
            else:
                logger.error(f"文件移动失败: {response.text}")
                result["status"] = "error"
                result["error_code"] = "MOVE_FAILED"
                result["message"] = f"移动失败: {response.text}"
                return result
        except Exception as e:
            logger.error(f"移动文件异常: {e}")
            result["status"] = "error"
            result["error_code"] = "MOVE_EXCEPTION"
            result["message"] = f"移动异常: {str(e)}"
            return result

    def get_file_list_recursive(self, folder_id, depth=0):
        """
        递归遍历指定文件夹下的所有子文件及子文件夹
        :param folder_id: 云盘文件夹ID
        :param depth: 当前递归深度，用于缩进显示
        :return: 文件夹下所有文件和文件夹的列表
        """
        result = {
            "status": "success",
            "folder_id": folder_id,
            "files": []
        }
        
        base_url = get_base_url()
        all_files = []
        next_cursor = None
        page_count = 0
        
        while True:
            page_count += 1
            url = f"{base_url}{DRIVE_URL_PATH}?fields=files(id,fileName,mimeType,size,editedTime),nextCursor&queryParam=parentFolder='{folder_id}'&pageSize=100"
            if next_cursor:
                url += f"&cursor={next_cursor}"
            
            headers = {
                "Authorization": self.auth
            }
            logger.info(f"get_file_list_recursive page {page_count}, url: {url}")
            
            try:
                response = requests.get(url, headers=headers, timeout=MAX_TIMEOUT)
                if check_token_expired(response):
                    result["status"] = "error"
                    result["error_code"] = "TOKEN_EXPIRED"
                    result["message"] = "授权已失效，请退出小艺Claw，再次启动小艺Claw重新获取授权后重试。"
                    return result
                
                if response.status_code == 200:
                    data = response.json()
                    files = data.get('files', [])
                    all_files.extend(files)
                    logger.info(f"get_file_list_recursive page {page_count}, files count: {len(files)}")
                    
                    next_cursor = data.get('nextCursor')
                    if not next_cursor:
                        break
                else:
                    logger.error(f"Response: {response.text}")
                    result["status"] = "error"
                    result["error_code"] = "QUERY_FAILED"
                    result["message"] = f"查询失败: {response.text}"
                    return result
            except Exception as e:
                logger.error(f"Error in get_file_list_recursive: {e}")
                result["status"] = "error"
                result["error_code"] = "QUERY_ERROR"
                result["message"] = f"查询异常: {str(e)}"
                return result
        
        # 递归处理子文件夹
        for file_info in all_files:
            file_info["depth"] = depth
            is_folder = file_info.get("mimeType") == "application/vnd.huawei-apps.folder"
            file_info["is_folder"] = is_folder
            result["files"].append(file_info)
            
            # 如果是文件夹，递归获取其内容
            if is_folder:
                sub_result = self.get_file_list_recursive(file_info["id"], depth + 1)
                if sub_result["status"] == "error":
                    return sub_result
                result["files"].extend(sub_result["files"])
        
        logger.info(f"Total files and folders in folder {folder_id}: {len(result['files'])}")
        return result

def parse_url(url):
    """
    解析 URL，提取 server_id 和 uploadId
    :param url: 完整的 URL
    :return: server_id 和 uploadId
    """
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split("/")
    query_params = parse_qs(parsed_url.query)

    server_id = path_parts[4] if len(path_parts) > 4 else None
    upload_id = query_params.get("uploadId", [None])[0]

    return server_id, upload_id


def get_properties(url, setting_key):
    try:
        response = requests.get(url, stream=True, timeout=MAX_TIMEOUT)
        response.raise_for_status()
        # 解析 JSON 内容
        try:
            content = response.json()
        except requests.exceptions.JSONDecodeError:
            logging.error("下载的文件不是有效的 JSON 格式。")
            return None

        # 读配置
        result = content.get(setting_key)
        logger.info(f"json content: {result}")
        return result
    except Exception as e:
        return None

def get_drive_token():
    with open(XIAO_YI_ENV_PATH, 'r') as file:
        content = file.read()
    # 使用正则表达式解析内容
    key_value_pattern = re.compile(r'([^=\s]+)\s*=\s*(.+)')
    config = key_value_pattern.findall(content)
    token = ""
    for key, value in config:
        if (key == "108635313_login_token"):
            token = value
    if token == "":
        for key, value in config:
            if (key == "USER_CREDENTIAL_TEMP_DRIVE_TOKEN"):
                token = value
    file.close()
    return token


def get_is_support_side_car():
    global global_support_sidecar
    with open(XIAO_YI_ENV_PATH, 'r') as file:
        content = file.read()
    # 使用正则表达式解析内容
    key_value_pattern = re.compile(r'([^=\s]+)\s*=\s*(.+)')
    config = key_value_pattern.findall(content)
    for key, value in config:
        if (key == "isSupportSideCar"):
            global_support_sidecar = value
    file.close()


def get_base_url():
    return get_properties(zip_input_files_url, "cloud_namespace_drive_base_url")

def set_upload_result(result, status, message):
    result["status"] = status
    result["message"] = message
    logger.info(json.dumps(result))
    print(json.dumps(result, ensure_ascii=False))


def query_space_detail(auth):
    """
    查询云空间详情
    :param auth: 认证token
    :return: int类型可用空间
    """
    hw_drive = UploadFileHwDrive(auth)
    result = hw_drive.get_space_detail()
    return result

def query_available_space(auth):
    """
    查询云空间剩余可用空间
    :param auth: 认证token
    :return: int类型可用空间
    """
    hw_drive = UploadFileHwDrive(auth)
    available_space = hw_drive.get_clouddrive_available_space()
    if available_space == "TOKEN_EXPIRED":
        print_token_expired()
        return -1
    logger.info(f"available space is {available_space}")
    return int(available_space)


def get_celiaclaw_file_list(auth):
    """
    查询文件是否存在
    :param auth: 认证token
    :return: 小艺Claw目录下的文件列表
    """
    hw_drive = UploadFileHwDrive(auth)
    folder_id = hw_drive.get_celiaclaw_file_id()
    if folder_id == "TOKEN_EXPIRED":
        print_token_expired()
        return "TOKEN_EXPIRED"
    if folder_id == "":
        print(f"{FOLDER_NOT_EXIST}")
        return f"{FOLDER_NOT_EXIST}"
    # 递归查询文件列表
    result = hw_drive.get_file_list_recursive(folder_id)
    print(result)
    return result

def query_file_exists(auth, file_name):
    """
    查询文件是否存在
    :param auth: 认证token
    :param file_name: 文件名
    :return: 0表示存在，1表示不存在
    """
    hw_drive = UploadFileHwDrive(auth)
    parent_folder_id = hw_drive.get_celiaclaw_file_id()
    if parent_folder_id == "TOKEN_EXPIRED":
        print_token_expired()
        return "TOKEN_EXPIRED"
    if parent_folder_id == "":
        # 文件夹不存在，文件也不存在
        print(f"{FILE_NOT_EXIST}")
        return f"{FILE_NOT_EXIST}"
    result = hw_drive.check_file_exists_recursive(file_name, parent_folder_id)
    print(result)
    return result


def query_folder_exists(auth, folder_name):
    """
    查询文件夹是否存在
    :param auth: 认证token
    :param folder_name: 文件夹名称
    :return: 0表示存在，1表示不存在,
    """
    hw_drive = UploadFileHwDrive(auth)
    result = hw_drive.check_folder_exists(folder_name)
    if result == "TOKEN_EXPIRED":
        print_token_expired()
    print(result)
    return result


def create_folder(auth, folder_name):
    """
    在云盘根路径下创建文件夹
    :param auth: 认证token
    :param folder_name: 文件夹名称
    """
    if (folder_name != PARENT_FOLDER_NAME):
        logger.error("the folder name is not allowed")
        return 1
    hw_drive = UploadFileHwDrive(auth)
    create_result = hw_drive.create_file_dir(folder_name, "root")
    if create_result == "TOKEN_EXPIRED":
        print_token_expired()
        return -1
    if create_result:
        logger.info(f"create the folder {folder_name} success")
        return 0
    else:
        logger.info(f"create the folder {folder_name} fail")
        return 1

def create_folder_in_parent(auth, folder_name, parent_folder_name):
    """
    在云盘指定路径下创建文件夹
    :param auth: 认证token
    :param folder_name: 文件夹名称
    :param parent_folder_name 父目录文件夹名称
    """
    hw_drive = UploadFileHwDrive(auth)
    celiaclaw_folder_id = hw_drive.get_celiaclaw_file_id()
    if celiaclaw_folder_id == "TOKEN_EXPIRED":
        print_token_expired()
        return "TOKEN_EXPIRED"
    if celiaclaw_folder_id == "":
        # 文件夹不存在，文件也不存在
        print(f"{FILE_NOT_EXIST}")
        return f"{FILE_NOT_EXIST}"
    parent_folder = hw_drive.check_file_exists_recursive(parent_folder_name, celiaclaw_folder_id)
    parent_folder_file = parent_folder["file"]
    parent_folder_id = parent_folder_file[0]["id"]
    create_result = hw_drive.create_file_dir(folder_name, parent_folder_id)
    print(json.dumps(create_result, ensure_ascii=False))
    return create_result

def download_file_from_celiaclaw(auth, file_id, download_path):
    """
    下载云盘文件
    :param auth: 认证token
    :param file_id: 云盘文件ID
    :param download_path: 本地下载路径
    :return: 下载结果字典
    """
    if auth == "":
        result = {
            "status": "error",
            "error_code": "TOKEN_EXPIRED",
            "message": "授权已失效，请退出小艺Claw，再次启动小艺Claw重新获取授权后重试。"
        }
        logger.error("auth is empty")
        print(json.dumps(result, ensure_ascii=False))
        return result
    
    hw_drive = UploadFileHwDrive(auth)
    result = hw_drive.download_file(file_id, download_path)
    
    if result["status"] == "error" and result.get("error_code") == "TOKEN_EXPIRED":
        print_token_expired()
        return result
    
    logger.info(json.dumps(result))
    print(json.dumps(result, ensure_ascii=False))
    return result


def rename_file_in_celiaclaw(auth, file_id, new_file_name):
    """
    重命名云盘文件
    :param auth: 认证token
    :param file_id: 云盘文件ID
    :param new_file_name: 新文件名
    :return: 重命名结果字典
    """
    if auth == "":
        result = {
            "status": "error",
            "error_code": "TOKEN_EXPIRED",
            "message": "授权已失效，请退出小艺Claw，再次启动小艺Claw重新获取授权后重试。"
        }
        logger.error("auth is empty")
        print(json.dumps(result, ensure_ascii=False))
        return result
    
    hw_drive = UploadFileHwDrive(auth)
    result = hw_drive.rename_file(file_id, new_file_name)
    
    if result["status"] == "error" and result.get("error_code") == "TOKEN_EXPIRED":
        print_token_expired()
        return result
    
    logger.info(json.dumps(result))
    print(json.dumps(result, ensure_ascii=False))
    return result


def move_file_to_folder(auth, file_id, source_parent_id, destination_parent_id):
    """
    移动文件到指定文件夹
    :param auth: 认证token
    :param file_id: 云盘文件ID
    :param source_parent_id: 原父目录ID
    :param destination_parent_id 目标父目录ID
    :return: 移动结果字典
    """
    if auth == "":
        result = {
            "status": "error",
            "error_code": "TOKEN_EXPIRED",
            "message": "授权已失效，请退出小艺Claw，再次启动小艺Claw重新获取授权后重试。"
        }
        logger.error("auth is empty")
        print(json.dumps(result, ensure_ascii=False))
        return result
    
    hw_drive = UploadFileHwDrive(auth)
    result = hw_drive.move_file(file_id, source_parent_id, destination_parent_id)
    
    if result["status"] == "error" and result.get("error_code") == "TOKEN_EXPIRED":
        print_token_expired()
        return result
    
    logger.info(json.dumps(result))
    print(json.dumps(result, ensure_ascii=False))
    return result


def query_folder_file_list(auth, folder_id):
    """
    递归查询指定文件夹下的所有子文件及子文件夹
    :param auth: 认证token
    :param folder_id: 件夹ID
    :return: 文件列表结果
    """
    if auth == "":
        result = {
            "status": "error",
            "error_code": "TOKEN_EXPIRED",
            "message": "授权失效，请退出小艺Claw，再次启动小艺Claw重新获取授权后重试。"
        }
        logger.error("auth is empty")
        print(json.dumps(result, ensure_ascii=False))
        return result
    
    hw_drive = UploadFileHwDrive(auth)
    result = hw_drive.get_file_list_recursive(folder_id)
    
    if result["status"] == "error" and result.get("error_code") == "TOKEN_EXPIRED":
        print_token_expired()
        return result
    
    # 打印所有文件信息
    logger.info(json.dumps(result))
    print(json.dumps(result, ensure_ascii=False))
    return result

def upload_file_to_drive(hw_drive, file_path, parent_folder_id, mode, result):
    try:
        # 创建云空间文件
        file_name = os.path.basename(file_path)
        file_size = str(os.path.getsize(file_path))
        space_check = hw_drive.check_space(int(file_size))
        if space_check == "TOKEN_EXPIRED":
            print_token_expired()
            return -1
        if not space_check:
            set_upload_result(result, "error", "云空间不足")
            return

        file_id = hw_drive.query_file(file_name, parent_folder_id)
        if file_id == "TOKEN_EXPIRED":
            print_token_expired()
            return -1
        if not file_id == "" and mode == "overwrite":
            create_resume_result = hw_drive.update_file_resume(file_name, file_id, file_size, parent_folder_id)
        else:
            create_resume_result = hw_drive.create_file_resume(
                f"{file_name}",
                parent_folder_id,
                file_size
            )

        if create_resume_result == "TOKEN_EXPIRED":
            print_token_expired()
            return -1
        if not create_resume_result:
            set_upload_result(result, "error", "文件创建失败")
            return
        slice_size = create_resume_result["sliceSize"]
        upload_url = create_resume_result["uploadUrl"]
        server_id, upload_id = parse_url(upload_url)

        # 上传文件
        resume_result = hw_drive.upload_file_in_chunks(
            server_id, upload_id, file_path, slice_size
        )
        if resume_result == "TOKEN_EXPIRED":
            print_token_expired()
            return -1
        if not resume_result:
            set_upload_result(result, "error", "文件上传失败")
            return
        result["file_id"] = resume_result
        set_upload_result(result, "success", "文件上传成功")
        return

    except Exception as e:
        logger.error(f"上传过程发生错误: {str(e)}")
        set_upload_result(result, "error", f"上传过程发生错误: {str(e)}")
        return

def upload_file_to_celiaclaw(auth, file_path, mode):
    """
    resume的方式上传指定文件到云空间
    """
    result = {
        "status": "success",
        "mode": "upload",
        "file_id": None,
        "file_path": file_path
    }
    if auth == "":
        set_upload_result(result, "error", "auth is empty")
        return
    if not os.path.exists(file_path):
        set_upload_result(result, "error", f"本地文件不存在: {file_path}")
        return
    hw_drive = UploadFileHwDrive(auth)
    parent_folder_id = hw_drive.get_celiaclaw_file_id()
    
    # 检测 token 是否过期
    if parent_folder_id == "TOKEN_EXPIRED":
        print_token_expired()
        return -1
    
    if parent_folder_id == "":
        # 创建小艺根目录
        create_folder_result = hw_drive.create_file_dir(PARENT_FOLDER_NAME, "root")
        if create_folder_result == "TOKEN_EXPIRED":
            print_token_expired()
            return -1
        if create_folder_result:
            parent_folder_id = create_folder_result["id"]
    if parent_folder_id == "":
        set_upload_result(result, "error", "创建文件夹失败")
        return

    try:
        # 创建云空间文件
        file_name = os.path.basename(file_path)
        file_size = str(os.path.getsize(file_path))
        space_check = hw_drive.check_space(int(file_size))
        if space_check == "TOKEN_EXPIRED":
            print_token_expired()
            return -1
        if not space_check:
            set_upload_result(result, "error", "云空间不足")
            return

        file_id = hw_drive.query_file(file_name, parent_folder_id)
        if file_id == "TOKEN_EXPIRED":
            print_token_expired()
            return -1
        if not file_id == "" and mode == "overwrite":
            create_resume_result = hw_drive.update_file_resume(file_name, file_id, file_size, parent_folder_id)
        else:
            create_resume_result = hw_drive.create_file_resume(
                f"{file_name}",
                parent_folder_id,
                file_size
            )

        if create_resume_result == "TOKEN_EXPIRED":
            print_token_expired()
            return -1
        if not create_resume_result:
            set_upload_result(result, "error", "文件创建失败")
            return
        slice_size = create_resume_result["sliceSize"]
        upload_url = create_resume_result["uploadUrl"]
        server_id, upload_id = parse_url(upload_url)

        # 上传文件
        resume_result = hw_drive.upload_file_in_chunks(
            server_id, upload_id, file_path, slice_size
        )
        if resume_result == "TOKEN_EXPIRED":
            print_token_expired()
            return -1
        if not resume_result:
            set_upload_result(result, "error", "文件上传失败")
            return
        result["file_id"] = resume_result
        set_upload_result(result, "success", "文件上传成功")
        return

    except Exception as e:
        logger.error(f"上传过程发生错误: {str(e)}")
        set_upload_result(result, "error", f"上传过程发生错误: {str(e)}")
        return

def upload_file_to_folder(auth, file_path, parent_folder_name, mode):
    result = {
        "status": "success",
        "mode": mode,
        "file_id": None,
        "file_path": file_path
    }
    hw_drive = UploadFileHwDrive(auth)
    celiaclaw_folder_id = hw_drive.get_celiaclaw_file_id()
    if celiaclaw_folder_id == "TOKEN_EXPIRED":
        print_token_expired()
        return "TOKEN_EXPIRED"
    if celiaclaw_folder_id == "":
        # 文件夹不存在，文件也不存在
        print(f"{FILE_NOT_EXIST}")
        return f"{FILE_NOT_EXIST}"
    parent_folder = hw_drive.check_file_exists_recursive(parent_folder_name, celiaclaw_folder_id)
    # if parent_folder.get("file")
    parent_folder_file = parent_folder["file"]
    parent_folder_id = parent_folder_file[0]["id"]
    upload_file_to_drive(hw_drive, file_path, parent_folder_id, mode, result)
    print(json.dumps(result, ensure_ascii=False))
    return result

def parse_arguments():
    parser = argparse.ArgumentParser(description="Huawei Cloud Drive CLI")
    parser.add_argument("--command", type=str, 
                        choices=["query", "query_folder", "upload", "create", "download", "rename", "move"],
                        help="命令类型: query, query_folder, upload, create, download, rename, move")
    parser.add_argument("--key", type=str, help="查询ID，用于query命令")
    parser.add_argument("--file_name", type=str, help="文件名，用于query或query_folder命令")
    parser.add_argument("--file_id", type=str, help="文件ID，用于download、rename和move命令")
    parser.add_argument("--source_parent_id", type=str, help="原父目录ID，用于move命令")
    parser.add_argument("--destination_parent_id", type=str, help="目标父目录ID，用于move命令")
    parser.add_argument("--mode", type=str, 
                        choices=["overwrite", "rename"],
                        help="上传模式: overwrite或rename")
    parser.add_argument("--folder_name", type=str, help="文件夹名称，用于create命令")
    parser.add_argument("--parent_folder_name", type=str, help="父目录名称，用于create命令")
    parser.add_argument("--path", type=str, help="文件路径: path=上传文件路径或download下载目标路径")
    parser.add_argument("--Authorization", type=str, help="用于云空间接口at")
    return parser.parse_args()

def main():
    args = parse_arguments()
    # 获取认证token
    if not args.Authorization:
        auth = get_drive_token()
    else:
        auth = args.Authorization
    if auth == "":
        logger.error("Authorization is empty")
        print(json.dumps({
            "status": "error",
            "error_code": "TOKEN_EXPIRED",
            "message": "授权已失效，请退出小艺Claw，再次启动小艺Claw重新获取授权后重试。"
        }, ensure_ascii=False))
        return -1
    # 根据command分发到不同处理逻辑
    command = args.command
    
    if command == "query":
        # 查询命令
        if args.key == "space":
            # 查询可用空间
            return query_space_detail(auth)
        elif args.key == "available_space":
            # 查询可用空间
            return query_available_space(auth)
        elif args.key == "file_list":
            if args.file_id:
                # 递归查询指定文件夹下的所有子文件及子文件夹
                return query_folder_file_list(auth, args.file_id)
            else:
                # 查询小艺Claw目录下的文件列表
                return get_celiaclaw_file_list(auth)
        elif args.file_name:
            # 查询文件是否存在
            return query_file_exists(auth, args.file_name)
        else:
            print("please specify --key available_space or --file_name <file_name>")
            sys.exit(1)
    
    elif command == "query_folder":
        # 查询文件夹是否存在
        if args.file_name:
            return query_folder_exists(auth, args.file_name)
        else:
            print("please specify --file_name <folder_name>")
            sys.exit(1)
    
    elif command == "upload":
        # 上传命令
        if not args.path:
            print("please input --path xxx")
            sys.exit(1)
        if not args.mode:
            print("please specify --mode overwrite or --mode rename")
            sys.exit(1)
        if not args.parent_folder_name:
            return upload_file_to_celiaclaw(auth, args.path, args.mode)
        return upload_file_to_folder(auth, args.path, args.parent_folder_name, args.mode)
    
    elif command == "create":
        # 创建文件夹命令
        if not args.folder_name:
            print("please specify --folder_name <folder_name>")
            sys.exit(1)
        if not args.parent_folder_name:
            return create_folder(auth, args.folder_name)
        return create_folder_in_parent(auth, args.folder_name, args.parent_folder_name)
    
    elif command == "download":
        # 下载文件命令
        if not args.file_id:
            print("please specify --file_id <file_id>")
            sys.exit(1)
        if not args.path:
            print("please specify --path <download_path>")
            sys.exit(1)
        return download_file_from_celiaclaw(auth, args.file_id, args.path)
    
    elif command == "rename":
        # 重命名文件命令
        if not args.file_id:
            print("please specify --file_id <file_id>")
            sys.exit(1)
        if not args.file_name:
            print("please specify --file_name <new_file_name>")
            sys.exit(1)
        return rename_file_in_celiaclaw(auth, args.file_id, args.file_name)
    
    elif command == "move":
        # 移动文件命令
        if not args.file_id:
            print("please specify --file_id <file_id>")
            sys.exit(1)
        if not args.source_parent_id:
            print("please specify --source_parent_id <source_parent_folder_id>")
            sys.exit(1)
        if not args.destination_parent_id:
            print("please specify --destination_parent_id <destination_parent_folder_id>")
            sys.exit(1)
        return move_file_to_folder(auth, args.file_id, args.source_parent_id, args.destination_parent_id)

if __name__ == "__main__":
    main()