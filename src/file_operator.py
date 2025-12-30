import aiofiles
from pathlib import Path


class FileOperator:
    def __init__(self, filepath: str):
        self.filepath = filepath

    async def read(self) -> str | None:
        """
        读取文件内容
        """
        try:
            async with aiofiles.open(self.filepath, 'r', encoding='utf-8') as f:
                content_str = await f.read()
                if content_str.strip():
                    return content_str
                else:
                    return None
        except FileNotFoundError:
            print(f"文件 {self.filepath} 不存在")
            return None
        except PermissionError:
            print(f"错误：没有权限读取文件 {self.filepath}")
            return None
        except Exception as e:
            print(f"读取文件 {self.filepath} 时发生错误: {e}")
            return None

    async def write(self, content: str) -> bool:
        """
        写入文件内容
        """
        try:
            Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(self.filepath, 'w', encoding='utf-8') as f:
                await f.write(content)
            return True

        except PermissionError:
            print(f"错误：没有权限写入文件 {self.filepath}")
            return False
        except Exception as e:
            print(f"写入文件 {self.filepath} 时发生错误: {e}")
            return False
