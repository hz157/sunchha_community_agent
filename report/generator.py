

def write_to_txt(file_path, content, mode="w", encoding="utf-8"):
    try:
        # 按行去除空白，并过滤掉空行
        lines = content.splitlines()  # 按行拆分
        cleaned_lines = [line.strip() for line in lines if line.strip()]  # 去掉空行和首尾空白
        if not cleaned_lines:  # 避免写入完全为空的内容
            print("⚠️ 仅包含空行，不执行写入！")
            return False

        # 写入文件
        with open(file_path, mode, encoding=encoding) as file:
            file.write("\n".join(cleaned_lines) + "\n")  # 保证正常换行
        return True
    except Exception as e:
        return False



