import os

print("正在检查.env文件的完整性...")

# 检查是否存在.env.example文件
if not os.path.exists('.env.example'):
    print("未找到.env.example文件，不执行任何操作。")
    exit()

# 读取.env.example的所有行
with open('.env.example', 'r', encoding='utf-8') as f:
    example_lines = f.readlines()

# 解析.env.example中的所有参数名
example_params = {}
for line in example_lines:
    stripped_line = line.strip()
    if stripped_line and not stripped_line.startswith('#') and '=' in stripped_line:
        param_name = line.split('=', 1)[0].strip()
        # 提取示例值
        rest_part = line.split('=', 1)[1]
        example_value = rest_part.lstrip().rstrip('\n')
        example_params[param_name] = example_value

# 解析.env文件中的参数（如果存在），只保留第一个出现的有效值
env_params = {}
env_exists = os.path.exists('.env')
if env_exists:
    with open('.env', 'r', encoding='utf-8') as f:
        for line in f:
            stripped_line = line.strip()
            if stripped_line and not stripped_line.startswith('#') and '=' in stripped_line:
                param_name = line.split('=', 1)[0].strip()
                rest_part = line.split('=', 1)[1]
                env_value = rest_part.lstrip().rstrip('\n')
                # 只保留第一个出现的参数值
                if param_name not in env_params:
                    env_params[param_name] = env_value

# 检查修复内容
fixed_content = []
if not env_exists:
    fixed_content.append("已创建.env文件")
else:
    # 检查缺失的参数
    missing_params = [p for p in example_params.keys() if p not in env_params.keys()]
    if missing_params:
        fixed_content.append(f"已补充缺失的参数名：{', '.join(missing_params)}")
    
    # 检查空值参数
    empty_value_params = [p for p in env_params.keys() if env_params[p] == '' and p in example_params and example_params[p] != '']
    if empty_value_params:
        fixed_content.append(f"已填充空参数值：{', '.join(empty_value_params)}")

# 生成新的.env文件内容
new_env_lines = []
for line in example_lines:
    stripped_line = line.strip()
    # 空行或注释直接保留
    if not stripped_line or stripped_line.startswith('#'):
        new_env_lines.append(line)
        continue
    
    # 处理参数行
    if '=' in line:
        # 找到第一个'='的位置
        equal_idx = line.index('=')
        param_part = line[:equal_idx]  # 参数名部分（包含原始空格）
        rest_part = line[equal_idx + 1:]  # '='后的部分
        
        # 提取'='后的前导空格
        leading_ws = rest_part[:len(rest_part) - len(rest_part.lstrip())]
        example_value = rest_part.lstrip().rstrip('\n')  # 提取示例值
        param_name = param_part.strip()  # 提取参数名
        
        # 检查.env中是否存在该参数
        if param_name in env_params:
            env_value = env_params[param_name]
            # 如果.env中有值则使用，否则使用示例值
            if env_value:
                new_line = f"{param_part}={leading_ws}{env_value}\n"
            else:
                new_line = line
        else:
            # 参数名缺失，直接使用示例行
            new_line = line
        new_env_lines.append(new_line)
    else:
        # 非参数、非空、非注释行，直接保留
        new_env_lines.append(line)

# 写入新的.env文件
with open('.env', 'w', encoding='utf-8') as f:
    f.writelines(new_env_lines)

# 输出检查修复结果
if fixed_content:
    for item in fixed_content:
        print(item)
else:
    print("未发现需要修复的问题")
print("已经检查修复完毕")
