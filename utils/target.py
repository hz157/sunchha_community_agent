import pandas as pd

def read_target_info(path: str = "target/target.xlsx"):
    try:
        # 读取 Excel，确保所有数据以字符串格式读取
        df = pd.read_excel(path, dtype=str)
        # 去除空白行
        df = df.dropna(how="all")
        # 去除列名前后空格，避免列名匹配问题
        df.rename(columns=lambda x: x.strip(), inplace=True)

        # 检查 command 列并设置为空的值为 None
        if 'command' in df.columns:
            df['command'] = df['command'].replace('/', None)  # 将空字符串替换为 None

        # 转换为字典列表
        data_list = df.to_dict(orient="records")
        return data_list

    except FileNotFoundError:
        print(f"错误: 文件 {path} 未找到！")
    except Exception as e:
        print(f"错误: 读取 Excel 文件失败，原因: {e}")

    return []  # 发生异常时返回空列表
