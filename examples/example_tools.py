"""
示例工具函数

这些工具函数演示了如何创建和注册工具供LLM调用。
在实际应用中，你可以实现更复杂的工具函数来访问外部API、数据库等。
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Literal


async def get_weather(
    location: str,
    unit: Literal["celsius", "fahrenheit"] = "celsius"
) -> dict:
    """
    获取指定地点的当前天气

    这是一个模拟函数，返回虚拟的天气数据。
    在实际应用中，你可以调用真实的天气API（如OpenWeatherMap）。

    Args:
        location: 地点，例如 "Paris, France" 或 "Tokyo, Japan"
        unit: 温度单位，celsius 或 fahrenheit

    Returns:
        包含天气信息的字典
    """
    # 模拟API延迟
    await asyncio.sleep(0.5)

    # 模拟天气数据（实际应用中应调用真实API）
    mock_weather = {
        "Paris, France": {"temp_c": 15, "condition": "Partly Cloudy", "humidity": 65},
        "Tokyo, Japan": {"temp_c": 22, "condition": "Sunny", "humidity": 45},
        "New York, USA": {"temp_c": 18, "condition": "Rainy", "humidity": 80},
        "London, UK": {"temp_c": 12, "condition": "Foggy", "humidity": 90},
        "Sydney, Australia": {"temp_c": 25, "condition": "Clear", "humidity": 50},
    }

    # 查找地点（不区分大小写）
    weather_data = None
    for key, value in mock_weather.items():
        if location.lower() in key.lower():
            weather_data = value
            break

    # 如果找不到地点，返回默认值
    if weather_data is None:
        weather_data = {"temp_c": 20, "condition": "Unknown", "humidity": 60}

    # 转换温度单位
    if unit == "fahrenheit":
        temp = weather_data["temp_c"] * 9/5 + 32
        temp_key = "temperature_f"
        temp_str = f"{temp:.1f}°F"
    else:
        temp = weather_data["temp_c"]
        temp_key = "temperature_c"
        temp_str = f"{temp}°C"

    return {
        "location": location,
        temp_key: temp,
        "temperature": temp_str,
        "condition": weather_data["condition"],
        "humidity": f"{weather_data['humidity']}%",
        "unit": unit
    }


async def get_current_time(timezone: str = "UTC") -> dict:
    """
    获取指定时区的当前时间

    Args:
        timezone: 时区名称，例如 "America/New_York", "Asia/Tokyo", "Europe/London"
                 支持的时区参见：https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

    Returns:
        包含时间信息的字典
    """
    try:
        # 获取指定时区的当前时间
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)

        return {
            "timezone": timezone,
            "datetime": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "time_12h": now.strftime("%I:%M:%S %p"),
            "weekday": now.strftime("%A"),
            "utc_offset": now.strftime("%z"),
        }
    except Exception as e:
        return {
            "error": f"Invalid timezone: {timezone}",
            "message": str(e),
            "hint": "Use timezone names like 'America/New_York', 'Asia/Tokyo', 'Europe/London', etc."
        }


async def calculate(expression: str) -> dict:
    """
    计算数学表达式

    Args:
        expression: 数学表达式，例如 "2 + 3 * 4" 或 "sqrt(16)"

    Returns:
        包含计算结果的字典
    """
    try:
        # 使用eval计算（注意：生产环境应使用更安全的方法）
        # 这里仅作演示，实际应用建议使用专门的数学表达式解析库
        import math

        # 允许的函数和常量
        safe_dict = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "pow": pow,
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "pi": math.pi,
            "e": math.e,
        }

        result = eval(expression, {"__builtins__": {}}, safe_dict)

        return {
            "expression": expression,
            "result": result,
            "formatted": f"{expression} = {result}"
        }
    except Exception as e:
        return {
            "error": f"Failed to calculate: {expression}",
            "message": str(e),
            "hint": "Use basic math operators (+, -, *, /, **) and functions like sqrt, sin, cos"
        }


def get_all_example_tools() -> dict:
    """
    获取所有示例工具函数

    Returns:
        工具名称到函数的映射字典
    """
    return {
        "get_weather": get_weather,
        "get_current_time": get_current_time,
        "calculate": calculate,
    }


def register_example_tools(tool_executor):
    """
    将所有示例工具注册到ToolExecutor

    Args:
        tool_executor: ToolExecutor实例

    Returns:
        注册的工具数量
    """
    tools = get_all_example_tools()

    for name, func in tools.items():
        tool_executor.register_tool(name, func)

    return len(tools)


# 使用示例
if __name__ == "__main__":
    async def main():
        # 测试get_weather
        print("Testing get_weather...")
        weather = await get_weather("Paris, France", "celsius")
        print(f"Weather: {weather}")

        # 测试get_current_time
        print("\nTesting get_current_time...")
        time_info = await get_current_time("Asia/Tokyo")
        print(f"Time: {time_info}")

        # 测试calculate
        print("\nTesting calculate...")
        calc_result = await calculate("2 + 3 * 4")
        print(f"Calculation: {calc_result}")

    asyncio.run(main())
