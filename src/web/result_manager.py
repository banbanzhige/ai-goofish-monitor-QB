import os
import re
import aiofiles
import json
from fastapi import APIRouter, HTTPException
from src.web.models import DeleteResultItemRequest, DeleteResultsBatchRequest


router = APIRouter()


def _extract_item_id(item):
    link = item.get("商品信息", {}).get("商品链接", "")
    match = re.search(r"id=(\d+)", link)
    return match.group(1) if match else ""


def _matches_filters(record, filters):
    if not filters:
        return True

    if filters.recommended_only:
        if record.get("ai_analysis", {}).get("is_recommended") is not True:
            return False

    if filters.task_name and filters.task_name != "all":
        if record.get("任务名称") != filters.task_name:
            return False

    if filters.keyword and filters.keyword != "all":
        if record.get("搜索关键字") != filters.keyword:
            return False

    if filters.ai_criteria and filters.ai_criteria != "all":
        if record.get("AI标准") != filters.ai_criteria:
            return False

    if filters.manual_keyword:
        manual_keyword_lower = filters.manual_keyword.lower()
        商品信息 = record.get("商品信息", {})
        商品标题 = 商品信息.get("商品标题", "").lower()
        商品描述 = 商品信息.get("商品描述", "").lower()
        卖家昵称 = 商品信息.get("卖家昵称", "").lower()
        当前售价 = 商品信息.get("当前售价", "").lower()
        AI建议 = record.get("ai_analysis", {}).get("reason", "").lower()

        if manual_keyword_lower not in 商品标题 and \
           manual_keyword_lower not in 商品描述 and \
           manual_keyword_lower not in 卖家昵称 and \
           manual_keyword_lower not in 当前售价 and \
           manual_keyword_lower not in AI建议:
            return False

    return True


async def _load_records(filepath):
    records = []
    async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
        async for line in f:
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError:
                continue
    return records


async def _write_records(filepath, records):
    async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
        for record in records:
            await f.write(json.dumps(record, ensure_ascii=False) + "\n")


async def _delete_records_in_file(filepath, filters, item_ids):
    records = await _load_records(filepath)
    initial_count = len(records)
    if item_ids:
        records = [record for record in records if _extract_item_id(record) not in item_ids]
    else:
        records = [record for record in records if not _matches_filters(record, filters)]
    deleted_count = initial_count - len(records)
    if deleted_count:
        await _write_records(filepath, records)
    return deleted_count


@router.get("/api/results/files")
async def list_result_files():
    """列出所有生成的 .jsonl 结果文件。"""
    jsonl_dir = "jsonl"
    if not os.path.isdir(jsonl_dir):
        return {"files": []}
    files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
    return {"files": files}


@router.delete("/api/results/files/{filename}")
async def delete_result_file(filename: str):
    """删除指定的结果文件。"""
    if filename == "all":
        jsonl_dir = "jsonl"
        if not os.path.isdir(jsonl_dir):
            return {"message": "结果文件目录未找到。"}

        files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
        if not files:
            return {"message": "没有结果文件需要删除。"}

        deleted_count = 0
        for file in files:
            try:
                filepath = os.path.join(jsonl_dir, file)
                os.remove(filepath)
                deleted_count += 1
            except Exception as e:
                print(f"删除文件 {file} 时出错: {e}")

        return {"message": f"已成功删除 {deleted_count} 个结果文件。"}

    if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名。")

    filepath = os.path.join("jsonl", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="结果文件未找到。")

    try:
        os.remove(filepath)
        return {"message": f"结果文件 '{filename}' 已成功删除。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除结果文件时出错: {e}")


@router.post("/api/results/delete")
async def delete_result_item(request: DeleteResultItemRequest):
    """从指定结果文件中删除指定的商品记录。"""
    try:
        filename = request.filename
        item_to_delete = request.item

        if filename == "all":
            jsonl_dir = "jsonl"
            if not os.path.isdir(jsonl_dir):
                raise HTTPException(status_code=404, detail="结果文件目录未找到。")

            files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
            if not files:
                raise HTTPException(status_code=404, detail="没有结果文件需要删除。")

            deleted_from_file = None
            found_record = False

            for file in files:
                filepath = os.path.join(jsonl_dir, file)

                records = []
                async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                    async for line in f:
                        try:
                            record = json.loads(line)
                            records.append(record)
                        except json.JSONDecodeError:
                            continue

                item_link = item_to_delete.get('商品信息', {}).get('商品链接', '')
                match = re.search(r'id=(\d+)', item_link)
                item_id_to_delete = match.group(1) if match else ''

                for i, record in enumerate(records):
                    record_link = record.get('商品信息', {}).get('商品链接', '')
                    match = re.search(r'id=(\d+)', record_link)
                    record_item_id = match.group(1) if match else ''

                    if record_item_id == item_id_to_delete:
                        records.pop(i)

                        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                            for record in records:
                                await f.write(json.dumps(record, ensure_ascii=False) + '\n')

                        found_record = True
                        deleted_from_file = file
                        break

                if found_record:
                    break

            if found_record:
                return {"message": f"商品记录已成功删除。", "file": deleted_from_file}
            else:
                raise HTTPException(status_code=404, detail="商品记录未找到。")

        if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="无效的文件名。")

        filepath = os.path.join("jsonl", filename)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="结果文件未找到。")

        records = []
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            async for line in f:
                try:
                    record = json.loads(line)
                    records.append(record)
                except json.JSONDecodeError:
                    continue

        found = False
        item_link = item_to_delete.get('商品信息', {}).get('商品链接', '')
        match = re.search(r'id=(\d+)', item_link)
        item_id_to_delete = match.group(1) if match else ''

        for i, record in enumerate(records):
            record_link = record.get('商品信息', {}).get('商品链接', '')
            match = re.search(r'id=(\d+)', record_link)
            record_item_id = match.group(1) if match else ''

            if record_item_id == item_id_to_delete:
                records.pop(i)

                async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                    for record in records:
                        await f.write(json.dumps(record, ensure_ascii=False) + '\n')
                return {"message": f"商品记录已成功删除。"}

        raise HTTPException(status_code=404, detail="商品记录未找到。")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除商品记录时出错: {e}")


@router.post("/api/results/delete-batch")
async def delete_results_batch(request: DeleteResultsBatchRequest):
    """按筛选条件或勾选项批量删除结果记录。"""
    filename = request.filename
    filters = request.filters
    item_ids = [item_id for item_id in (request.item_ids or []) if item_id]

    if filename != "all":
        if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="无效的文件名。")

        filepath = os.path.join("jsonl", filename)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="结果文件未找到。")

        deleted_count = await _delete_records_in_file(filepath, filters, item_ids)
        return {
            "message": f"已删除 {deleted_count} 条记录。",
            "deleted_count": deleted_count,
            "files": [filename]
        }

    jsonl_dir = "jsonl"
    if not os.path.isdir(jsonl_dir):
        raise HTTPException(status_code=404, detail="结果文件目录未找到。")

    files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]
    if not files:
        raise HTTPException(status_code=404, detail="没有结果文件需要删除。")

    total_deleted = 0
    touched_files = []
    for file in files:
        filepath = os.path.join(jsonl_dir, file)
        deleted_count = await _delete_records_in_file(filepath, filters, item_ids)
        if deleted_count:
            total_deleted += deleted_count
            touched_files.append(file)

    return {
        "message": f"已删除 {total_deleted} 条记录。",
        "deleted_count": total_deleted,
        "files": touched_files
    }


@router.get("/api/results/{filename}")
async def get_result_file_content(filename: str, page: int = 1, limit: int = 20, recommended_only: bool = False, task_name: str = None, keyword: str = None, ai_criteria: str = None, sort_by: str = "crawl_time", sort_order: str = "desc", manual_keyword: str = None):
    """读取指定的 .jsonl 文件内容，支持分页、筛选和排序。"""
    results = []

    if filename == "all":
        jsonl_dir = "jsonl"
        if not os.path.isdir(jsonl_dir):
            raise HTTPException(status_code=404, detail="结果文件目录未找到。")

        files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]

        for file in files:
            filepath = os.path.join(jsonl_dir, file)
            try:
                async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                    async for line in f:
                        try:
                            record = json.loads(line)
                            results.append(record)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"读取文件 {file} 时出错: {e}")
                continue
    else:
        if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="无效的文件名。")

        filepath = os.path.join("jsonl", filename)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="结果文件未找到。")

        try:
            async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                async for line in f:
                    try:
                        record = json.loads(line)
                        results.append(record)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"读取结果文件时出错: {e}")

    filtered_results = []
    for record in results:
        match = True

        if recommended_only:
            if record.get("ai_analysis", {}).get("is_recommended") is not True:
                match = False

        if task_name and task_name != "all":
            if record.get("任务名称") != task_name:
                match = False

        if keyword and keyword != "all":
            if record.get("搜索关键字") != keyword:
                match = False

        if ai_criteria and ai_criteria != "all":
            if record.get("AI标准") != ai_criteria:
                match = False

        if manual_keyword:
            manual_keyword_lower = manual_keyword.lower()
            商品信息 = record.get("商品信息", {})
            商品标题 = 商品信息.get("商品标题", "").lower()
            商品描述 = 商品信息.get("商品描述", "").lower()
            卖家昵称 = 商品信息.get("卖家昵称", "").lower()
            当前售价 = 商品信息.get("当前售价", "").lower()
            AI建议 = record.get("ai_analysis", {}).get("reason", "").lower()

            if manual_keyword_lower not in 商品标题 and \
               manual_keyword_lower not in 商品描述 and \
               manual_keyword_lower not in 卖家昵称 and \
               manual_keyword_lower not in 当前售价 and \
               manual_keyword_lower not in AI建议:
                match = False

        if match:
            filtered_results.append(record)

    def get_sort_key(item):
        info = item.get("商品信息", {})
        if sort_by == "publish_time":
            return info.get("发布时间", "0000-00-00 00:00")
        elif sort_by == "price":
            price_str = str(info.get("当前售价", "0")).replace("¥", "").replace(",", "").strip()
            try:
                return float(price_str)
            except (ValueError, TypeError):
                return 0.0
        else:
            return item.get("公开信息浏览时间", "")

    is_reverse = (sort_order == "desc")
    filtered_results.sort(key=get_sort_key, reverse=is_reverse)

    total_items = len(filtered_results)
    start = (page - 1) * limit
    end = start + limit
    paginated_results = filtered_results[start:end]

    tasks = []
    try:
        async with aiofiles.open("config.json", "r", encoding="utf-8") as f:
            tasks = json.loads(await f.read())
    except Exception as e:
        print(f"读取任务配置时出错: {e}")

    return {
        "total_items": total_items,
        "page": page,
        "limit": limit,
        "items": paginated_results,
        "tasks": tasks
    }
