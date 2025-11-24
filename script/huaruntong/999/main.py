"""
答题主程序
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from api import QuizAPI

# 添加项目根目录到Python路径以导入notification模块
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent.parent
sys.path.insert(0, str(project_root))

from notification import send_notification, NotificationSound


def load_config():
    """加载统一配置文件"""
    # 使用统一的 token.json 配置文件
    # 从当前文件位置向上三级到达项目根目录，然后进入 config 目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, '..', '..', '..', 'config', 'token.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_correct_answer(question_data):
    """
    从题目数据中找出正确答案

    :param question_data: 题目数据
    :return: 正确答案的选项代码列表
    """
    options = question_data.get('question', {}).get('options', [])
    correct_options = []

    for option in options:
        if option.get('right'):
            correct_options.append(option.get('optionCode'))

    return correct_options


def process_account(account_config):
    """处理单个账号的答题"""
    account_name = account_config.get('account_name', '未知账号')

    # 初始化结果
    result_info = {
        'account_name': account_name,
        'mobile': account_config['mobile'],
        'success': False,
        'error': None,
        'question': None,
        'answer': None
    }

    # 初始化 API
    api = QuizAPI(
        token=account_config["token"],
        mobile=account_config["mobile"],
        user_agent=account_config.get("user_agent")
    )

    print("=" * 50)
    print(f"账号: {account_name} ({account_config['mobile']})")
    print("开始答题...")
    print("=" * 50)

    # 获取题目
    print("\n📝 正在获取题目...")
    result = api.get_question()

    if result.get('resultCode') != '0':
        error_msg = result.get('message', '未知错误')
        print(f"❌ 获取题目失败: {error_msg}")
        result_info['error'] = f"获取题目失败: {error_msg}"
        return result_info

    # 解析题目
    question_data = result.get('data', {}).get('knowledgeQuestionData')
    if not question_data:
        print("❌ 题目数据为空")
        result_info['error'] = '题目数据为空'
        return result_info

    question_id = question_data.get('questionId')
    question_text = question_data.get('question', {}).get('questionContents', [''])[0]
    options = question_data.get('question', {}).get('options', [])

    # 限制题目长度用于通知
    result_info['question'] = question_text[:30] + '...' if len(question_text) > 30 else question_text

    print(f"\n题目: {question_text}")
    print("\n选项:")
    for option in options:
        option_code = option.get('optionCode')
        option_text = option.get('optionContents', [''])[0]
        is_right = "✅" if option.get('right') else ""
        print(f"  {option_code}. {option_text} {is_right}")

    # 找出正确答案
    correct_options = find_correct_answer(question_data)
    if not correct_options:
        print("\n❌ 未找到正确答案")
        result_info['error'] = '未找到正确答案'
        return result_info

    result_info['answer'] = ', '.join(correct_options)
    print(f"\n💡 正确答案: {result_info['answer']}")

    # 提交答案
    print("\n📤 正在提交答案...")
    submit_result = api.submit_answer(question_id, correct_options)

    if submit_result.get('resultCode') == '0':
        print("✅ 答题成功!")
        print(f"响应数据: {submit_result}")
        result_info['success'] = True
    else:
        error_msg = submit_result.get('message', '未知错误')
        print(f"❌ 答题失败: {error_msg}")
        result_info['error'] = f"答题失败: {error_msg}"

    print("\n" + "=" * 50)
    return result_info


def send_notification_summary(all_results, start_time, end_time):
    """
    发送任务执行结果的推送通知

    Args:
        all_results: 所有账号的执行结果列表
        start_time: 任务开始时间
        end_time: 任务结束时间
    """
    try:
        duration = (end_time - start_time).total_seconds()

        # 统计结果
        total_count = len(all_results)
        success_count = sum(1 for r in all_results if r.get('success'))
        failed_count = total_count - success_count

        # 构建通知标题
        if failed_count == 0:
            title = "华润通999答题成功 ✅"
            sound = NotificationSound.BIRDSONG
        elif success_count == 0:
            title = "华润通999答题失败 ❌"
            sound = NotificationSound.ALARM
        else:
            title = "华润通999答题部分成功 ⚠️"
            sound = NotificationSound.BELL

        # 构建通知内容
        content_parts = [
            "📊 执行统计:",
            f"✅ 成功: {success_count} 个账号",
            f"❌ 失败: {failed_count} 个账号",
            f"📈 总计: {total_count} 个账号",
            "",
            "📝 详情:"
        ]

        for result in all_results:
            account_name = result.get('account_name', '未知账号')
            if result.get('success'):
                content_parts.append(f"  ✅ [{account_name}] 答题成功")
            else:
                error = result.get('error', '未知错误')
                if len(error) > 30:
                    error = error[:30] + "..."
                content_parts.append(f"  ❌ [{account_name}] {error}")

        content_parts.append("")
        content_parts.append(f"⏱️ 执行耗时: {int(duration)}秒")
        content_parts.append(f"🕐 完成时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        content = "\n".join(content_parts)

        # 发送通知
        send_notification(
            title=title,
            content=content,
            sound=sound,
            group="华润通999"
        )
        print("✅ 推送通知发送成功")

    except Exception as e:
        print(f"❌ 推送通知失败: {str(e)}")


def main():
    """主函数"""
    # 记录开始时间
    start_time = datetime.now()
    print(f"\n{'='*60}")
    print(f"## 华润通999答题任务开始")
    print(f"## 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 加载配置
    config = load_config()
    accounts = config.get('huaruntong', {}).get('999', {}).get('accounts', [])

    if not accounts:
        print("❌ 配置文件中没有找到账号信息")
        return

    # 收集所有账号的结果
    all_results = []

    # 遍历所有账号
    for account in accounts:
        if not account.get('token'):
            print(f"⚠️  跳过账号 {account.get('account_name', '未知')}: token 为空")
            print("=" * 50)
            all_results.append({
                'account_name': account.get('account_name', '未知'),
                'success': False,
                'error': 'token为空'
            })
            continue

        result = process_account(account)
        all_results.append(result)
        print("\n")

    # 记录结束时间
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"\n{'='*60}")
    print(f"## 华润通999答题任务完成")
    print(f"## 结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"## 执行耗时: {int(duration)} 秒")
    print(f"{'='*60}\n")

    # 发送推送通知
    send_notification_summary(all_results, start_time, end_time)


if __name__ == "__main__":
    main()

