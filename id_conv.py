import pandas as pd
import os


def process_csv_conversion():
    input_file = 'id_conv_before.csv'  # 包含待查询PMID的文件
    database_file = 'PMC-ids.csv'  # 包含完整信息的数据库文件
    output_file = 'id_conv_after.csv'  # 结果文件

    # 1. 读取第一个文件 (包含PMID列表)
    # 这里的 encoding='utf-8-sig' 是为了更好兼容包含中文的CSV，如果报错可以尝试 'gbk'
    print(f"正在读取 {input_file} ...")
    try:
        df_target = pd.read_csv(input_file, encoding='utf-8-sig')
    except UnicodeDecodeError:
        df_target = pd.read_csv(input_file, encoding='gbk')

    # 确保列名没有前后空格
    df_target.columns = df_target.columns.str.strip()

    if 'PMID' not in df_target.columns:
        print(f"错误：在 {input_file} 中未找到 'PMID' 列")
        return

    # 2. 读取第二个文件 (数据库)
    # low_memory=False 防止大文件读取时出现警告
    print(f"正在读取 {database_file} ...")
    try:
        df_source = pd.read_csv(database_file, low_memory=False)
    except Exception as e:
        print(f"读取数据库文件失败: {e}")
        return

    df_source.columns = df_source.columns.str.strip()

    # 检查数据库文件是否包含必要列
    required_cols = ['PMID', 'DOI', 'PMCID']
    for col in required_cols:
        if col not in df_source.columns:
            print(f"错误：在 {database_file} 中未找到 '{col}' 列。请检查表头。")
            return

    # 3. 数据清洗与格式统一
    print("正在进行数据匹配...")

    # 将PMID统一转换为字符串，并去除可能的浮点数后缀（如 "123.0" -> "123"）
    # errors='coerce' 会将无法转换的值设为NaN，fillna('') 将其填充为空字符串
    df_target['PMID'] = df_target['PMID'].astype(str).str.replace(r'\.0$', '', regex=True)
    df_source['PMID'] = df_source['PMID'].astype(str).str.replace(r'\.0$', '', regex=True)

    # 4. 执行合并 (Left Join)
    # 以第一个文件的PMID为准，去第二个文件中找对应的 DOI 和 PMCID
    # 只提取 source 中的 PMID, DOI, PMCID 三列参与合并
    merged_df = pd.merge(
        df_target[['PMID']],  # 左表：只取第一份文件的PMID列
        df_source[['PMID', 'DOI', 'PMCID']],  # 右表：取数据库的相关列
        on='PMID',  # 匹配键
        how='left'  # 左连接：保留左表所有行，匹配不到的填NaN
    )

    # 5. 整理结果列顺序
    # 确保顺序为 PMID, DOI, PMCID
    final_df = merged_df[['PMID', 'DOI', 'PMCID']]

    # 6. 保存结果
    print(f"正在保存结果到 {output_file} ...")
    final_df.to_csv(output_file, index=False, encoding='utf-8-sig')

    print("-" * 30)
    print(f"处理完成！")
    print(f"输入行数: {len(df_target)}")
    print(f"输出行数: {len(final_df)}")
    print(f"匹配成功数: {final_df['DOI'].notna().sum()}")  # 统计DOI不为空的行数作为参考

    # 预览前5行
    print("\n前5行预览：")
    print(final_df.head())


if __name__ == "__main__":
    process_csv_conversion()