import json
import numpy as np
from typing import Union, Dict, List, Any

def extract_main_text_from_json(json_source: Union[str, Dict[str, Any]]) -> str:
    """
    从指定的JSON数据中提取主要文本内容
    
    参数:
        json_source: 可以是JSON文件路径（str），也可以是已加载的JSON字典（Dict）
    
    返回:
        str: 提取并拼接后的主要文本
    """
    # 1. 加载JSON数据
    if isinstance(json_source, str):
        try:
            with open(json_source, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"JSON文件不存在: {json_source}")
        except json.JSONDecodeError:
            raise ValueError(f"JSON文件格式错误，无法解析: {json_source}")
    elif isinstance(json_source, dict):
        json_data = json_source
    else:
        raise TypeError(f"json_source必须是文件路径(str)或字典(Dict)，当前类型: {type(json_source)}")
    
    # 2. 校验并提取核心字段
    main_text_parts = []
    
    # 检查是否启用了文档预处理
    if json_data.get('use_doc_preprocessor', False):
        doc_preprocessor_res = json_data.get('doc_preprocessor_res', {})
        parsing_res_list = doc_preprocessor_res.get('parsing_res_list', [])
    else:
        # 如果未启用预处理，直接从根节点找parsing_res_list（兼容不同场景）
        parsing_res_list = json_data.get('parsing_res_list', [])
    
    # 3. 遍历解析结果列表，提取文本
    if not parsing_res_list:
        print("警告: 未找到parsing_res_list字段，或该列表为空")
        return ""
    
    # 按block_order排序（None值排最后）
    def get_block_order(block: Dict) -> int:
        order = block.get('block_order')
        return float('inf') if order is None else order
    
    sorted_parsing_res = sorted(parsing_res_list, key=get_block_order)
    
    # 提取每个block的文本内容
    for idx, block in enumerate(sorted_parsing_res):
        block_content = block.get('block_content', '')
        block_label = block.get('block_label', 'unknown')
        block_id = block.get('block_id', idx)
        
        # 仅保留非空的文本内容
        if block_content.strip():
            # 可选：添加标签注释（方便调试，不需要可以删除）
            # main_text_parts.append(f"【{block_label}-{block_id}】{block_content}")
            main_text_parts.append(block_content)
    
    # 4. 拼接所有文本部分
    main_text = '\n\n'.join(main_text_parts)
    
    return main_text

# ------------------- 示例使用 -------------------
if __name__ == "__main__":
    # 使用示例1: 从JSON文件提取
    # json_file_path = "your_json_file.json"  # 替换为你的JSON文件路径
    # main_text = extract_main_text_from_json(json_file_path)
    
    # 使用示例2: 从已加载的JSON字典提取（测试用）
    test_json_data = {
        "input_path": "test.pdf",
        "page_index": 0,
        "model_settings": {"use_ocr": True},
        "use_doc_preprocessor": True,
        "use_layout_detection": True,
        "use_chart_recognition": False,
        "format_block_content": True,
        "doc_preprocessor_res": {
            "input_path": None,
            "page_index": None,
            "model_settings": {"use_doc_orientation_classify": True, "use_doc_unwarping": True},
            "angle": 0,
            "parsing_res_list": [
                {"block_bbox": [10, 10, 200, 50], "block_label": "text", "block_content": "这是第一段主要文本", "block_id": 0, "block_order": 1},
                {"block_bbox": [10, 60, 200, 100], "block_label": "text", "block_content": "这是第二段主要文本", "block_id": 1, "block_order": 2},
                {"block_bbox": [10, 110, 200, 150], "block_label": "table", "block_content": "姓名\t年龄\n张三\t25", "block_id": 2, "block_order": 3}
            ]
        }
    }
    
    # 执行提取
    main_text = extract_main_text_from_json(test_json_data)
    
    # 输出结果
    print("=== 提取的主要文本 ===")
    print(main_text)