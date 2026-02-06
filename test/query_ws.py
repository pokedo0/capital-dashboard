"""
Yahoo Finance WebSocket Streaming - 获取实时 overnight 数据

通过 WebSocket 连接 Yahoo Finance 实时数据流
消息使用 base64 编码的 protobuf 格式
"""
import asyncio
import base64
import json
import struct
from datetime import datetime
from websockets import connect


def decode_protobuf_varint(data, offset):
    """解码 protobuf varint"""
    result = 0
    shift = 0
    while True:
        if offset >= len(data):
            return None, offset
        byte = data[offset]
        result |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80):
            break
        shift += 7
    return result, offset


def decode_yahoo_pricing(data: bytes) -> dict:
    """
    解码 Yahoo Finance pricing protobuf 消息
    字段定义（通过逆向工程得到）:
    1: string id (股票代码)
    2: float price
    3: int64 time
    4: string currency
    5: string exchange
    6: int32 quoteType
    7: int32 marketHours
    8: float changePercent
    9: int64 dayVolume
    10: float dayHigh
    11: float dayLow
    12: float change
    13: string shortName
    14: int64 expireDate
    15: float openPrice
    16: float previousClose
    17: float strikePrice
    18: string underlyingSymbol
    19: int64 openInterest
    20: int64 optionsType
    21: int64 miniOption
    22: int64 lastSize
    23: float bid
    24: float bidSize
    25: float ask
    26: float askSize
    27: float priceHint
    """
    result = {}
    offset = 0
    
    while offset < len(data):
        # 读取 field tag
        tag, offset = decode_protobuf_varint(data, offset)
        if tag is None:
            break
            
        field_num = tag >> 3
        wire_type = tag & 0x07
        
        # wire_type: 0=varint, 1=64bit, 2=length-delimited, 5=32bit
        if wire_type == 0:  # varint
            value, offset = decode_protobuf_varint(data, offset)
            if field_num == 3:
                result['time'] = value
            elif field_num == 6:
                result['quoteType'] = value
            elif field_num == 7:
                result['marketHours'] = ['UNKNOWN', 'PRE_MARKET', 'REGULAR', 'POST_MARKET', 'EXTENDED_HOURS'][value] if value < 5 else value
            elif field_num == 9:
                result['dayVolume'] = value
                
        elif wire_type == 1:  # 64-bit
            value = struct.unpack('<d', data[offset:offset+8])[0] if offset + 8 <= len(data) else None
            offset += 8
            
        elif wire_type == 2:  # length-delimited (string/bytes)
            length, offset = decode_protobuf_varint(data, offset)
            if length and offset + length <= len(data):
                value = data[offset:offset+length]
                offset += length
                try:
                    str_value = value.decode('utf-8')
                    if field_num == 1:
                        result['id'] = str_value
                    elif field_num == 4:
                        result['currency'] = str_value
                    elif field_num == 5:
                        result['exchange'] = str_value
                    elif field_num == 13:
                        result['shortName'] = str_value
                except:
                    pass
                    
        elif wire_type == 5:  # 32-bit (float)
            if offset + 4 <= len(data):
                value = struct.unpack('<f', data[offset:offset+4])[0]
                offset += 4
                if field_num == 2:
                    result['price'] = round(value, 4)
                elif field_num == 8:
                    result['changePercent'] = round(value, 4)
                elif field_num == 10:
                    result['dayHigh'] = round(value, 4)
                elif field_num == 11:
                    result['dayLow'] = round(value, 4)
                elif field_num == 12:
                    result['change'] = round(value, 4)
                elif field_num == 15:
                    result['openPrice'] = round(value, 4)
                elif field_num == 16:
                    result['previousClose'] = round(value, 4)
            else:
                offset = len(data)
        else:
            # 未知类型，跳过
            break
            
    return result


async def stream_yahoo_finance(symbols: list, on_message=None, duration_seconds: int = 30):
    """
    连接 Yahoo Finance WebSocket 获取实时数据
    
    Args:
        symbols: 股票代码列表，如 ["NVDA", "QQQ"]
        on_message: 回调函数，接收解码后的消息
        duration_seconds: 运行时长（秒）
    """
    uri = "wss://streamer.finance.yahoo.com/?version=2"
    
    print(f"正在连接 {uri}...")
    
    async with connect(uri) as websocket:
        print("连接成功!")
        
        # 发送订阅请求
        subscribe_msg = json.dumps({"subscribe": symbols})
        await websocket.send(subscribe_msg)
        print(f"已订阅: {symbols}")
        print(f"运行 {duration_seconds} 秒后自动停止...\n")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            while True:
                # 检查是否超时
                if asyncio.get_event_loop().time() - start_time > duration_seconds:
                    print("\n时间到，断开连接")
                    break
                
                try:
                    # 等待消息，设置超时
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    
                    # 解析 JSON 消息
                    msg_json = json.loads(message)
                    
                    if msg_json.get("type") == "pricing":
                        # 解码 base64 编码的 protobuf 数据
                        encoded_data = msg_json.get("message", "")
                        try:
                            decoded_bytes = base64.b64decode(encoded_data)
                            pricing_data = decode_yahoo_pricing(decoded_bytes)
                            
                            if on_message:
                                on_message(pricing_data)
                            else:
                                print_pricing(pricing_data)
                        except Exception as e:
                            print(f"解码错误: {e}")
                            
                except asyncio.TimeoutError:
                    print(".", end="", flush=True)
                    
        except KeyboardInterrupt:
            print("\n用户中断")


def print_pricing(data: dict):
    """打印价格数据"""
    if not data.get('id'):
        return
        
    now = datetime.now().strftime('%H:%M:%S')
    market_hours = data.get('marketHours', 'N/A')
    
    # 市场状态颜色标识
    status_icon = {
        'PRE_MARKET': '🌅',
        'REGULAR': '📈',
        'POST_MARKET': '🌙',
        'EXTENDED_HOURS': '🌃'
    }.get(market_hours, '❓')
    
    print(f"[{now}] {status_icon} {data.get('id', 'N/A'):6} | "
          f"价格: {data.get('price', 'N/A'):>10} | "
          f"涨跌: {data.get('change', 0):>+8.2f} | "
          f"涨跌幅: {data.get('changePercent', 0):>+6.2f}% | "
          f"市场: {market_hours}")


if __name__ == "__main__":
    print("="*70)
    print("Yahoo Finance WebSocket 实时数据流")
    print("="*70)
    
    # 运行 30 秒
    asyncio.run(stream_yahoo_finance(
        symbols=["NVDA", "QQQ", "AAPL"],
        duration_seconds=30
    ))
