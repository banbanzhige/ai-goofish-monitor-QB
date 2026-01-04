import os

print("正在检查.env文件的完整性...")

# 检查是否存在.env.example文件
if not os.path.exists('.env.example'):
    print("未找到.env.example文件，不执行任何操作。")
    exit()

# 步骤1: 如果没有.env文件，将.env.example复制为.env
if not os.path.exists('.env'):
    with open('.env.example', 'r', encoding='utf-8') as example_file, \
         open('.env', 'w', encoding='utf-8') as new_env_file:
        new_env_file.write(example_file.read())
    print("已创建.env文件")
else:
    # 步骤2-4: 比较.env和.env.example
    with open('.env.example', 'r', encoding='utf-8') as example_file:
        example_content = example_file.readlines()
    
    with open('.env', 'r', encoding='utf-8') as env_file:
        env_content = env_file.readlines()
    
    # 解析.env.example的参数
    example_params = {}
    example_lines_dict = {}  # 保存每个参数名对应的完整行
    
    for line in example_content:
        stripped_line = line.strip()
        if stripped_line and not stripped_line.startswith('#') and '=' in stripped_line:
            param_name = line.split('=', 1)[0].strip()
            # 提取示例值
            rest_part = line.split('=', 1)[1]
            example_value = rest_part.lstrip().rstrip('\n')
            example_params[param_name] = example_value
            example_lines_dict[param_name] = line
    
    # 解析当前.env的参数
    current_env_params = {}
    
    for line in env_content:
        stripped_line = line.strip()
        if stripped_line and not stripped_line.startswith('#') and '=' in stripped_line:
            param_name = line.split('=', 1)[0].strip()
            rest_part = line.split('=', 1)[1]
            current_value = rest_part.lstrip().rstrip('\n')
            current_env_params[param_name] = current_value
    
    # 生成新的.env内容，保持与.env.example相同的格式
    new_env_content = []
    missing_params = []
    filled_params = []
    
    for line in example_content:
        stripped_line = line.strip()
        
        # 保留注释和空行
        if not stripped_line or stripped_line.startswith('#'):
            new_env_content.append(line)
        elif '=' in line:  # 参数行
            param_name = line.split('=', 1)[0].strip()
            
            # 检查参数是否存在于当前.env
            if param_name in current_env_params:
                # 参数存在，检查是否有值
                if current_env_params[param_name]:
                    # 参数有值，保持格式并替换值
                    # 找到行中'='的位置
                    equal_pos = line.index('=')
                    param_part = line[:equal_pos]
                    ws_part = line[equal_pos + 1 : len(line) - len(line[equal_pos + 1:].lstrip())].rstrip('\n')
                    new_env_content.append(f"{param_part}={ws_part}{current_env_params[param_name]}\n")
                else:
                    # 参数没有值，使用.env.example的值
                    new_env_content.append(line)
            else:
                # 参数缺失，添加完整行
                new_env_content.append(line)
                missing_params.append(param_name)
        else:
            # 非参数行（不包含'='且不是空行或注释）直接保留
            new_env_content.append(line)
    
    # 将结果写入.env文件
    with open('.env', 'w', encoding='utf-8') as env_file:
        env_file.writelines(new_env_content)
    
    # 输出检查修复结果
    fixed_content = []
    if missing_params:
        fixed_content.append(f"已补充缺失的参数名：{', '.join(missing_params)}")
    
    filled_params = [p for p in current_env_params.keys() if current_env_params[p] == '' and p in example_params and example_params[p] != '']
    if filled_params:
        fixed_content.append(f"已填充空参数值：{', '.join(filled_params)}")
    
    if fixed_content:
        for item in fixed_content:
            print(item)
    else:
        print("未发现需要修复的问题")

print("已经检查修复完毕")
