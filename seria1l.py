import serial
import time
import binascii # 可选，用于打印调试信息
#    超时时间: 读取串口时的等待时间（秒），这里主要用发送，设置短一点
port = '/dev/ttyHS1'
baudrate = 9600
timeout = 1#    超时时间: 读取串口时的等待时间（秒），这里主要用发送，设置短一点

try:
    # 2. 打开串口
    #    write_timeout 设置为 None 表示阻塞直到所有数据发送完毕
    ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout, write_timeout=None)
    
    if ser.is_open:
        print(f"成功打开串口 {port}，波特率 {baudrate}")
        ascii_data = "01" 
        ascii_bytes = ascii_data.encode('utf-8') # 或者直接用 b'01'
        bytes_sent = ser.write(ascii_bytes)
except serial.SerialException as e:
    print(f"串口错误: {e}")
except Exception as e:
    print(f"其他错误: {e}")
finally:
    # 3. 关闭串口
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("串口已关闭")