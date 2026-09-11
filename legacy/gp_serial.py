import serial
import serial.tools.list_ports
import threading
import time

class SerialManager:
    """简单的串口管理类"""
    def __init__(self, port='/dev/ttyHS1', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.lock = threading.Lock()
        
    def connect(self):
        """连接串口"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
            print(f"串口连接成功: {self.port} @ {self.baudrate} baud")
            return True
        except Exception as e:

            
            # 尝试列出可用串口作为参考
            try:
                ports = serial.tools.list_ports.comports()
                if ports:
                    print(f"\n可用串口:")
                    for p in ports:
                        print(f"  - {p.device} ({p.description})")
            except:
                pass
                
            return False
    
    def send(self, data):
        """发送数据"""
        if self.serial and self.serial.is_open:
            with self.lock:
                try:
                    if isinstance(data, str):
                        data = data.encode()
                    self.serial.write(data)
                    print(f"串口发送: {data}")
                    return True
                except Exception as e:
                    print(f"串口发送失败: {e}")
                    return False
        else:
            print(f"串口未连接，尝试重新连接...")
            if self.connect():
                return self.send(data)
        return False
    
    def close(self):
        """关闭串口"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            print(f"串口 {self.port} 已关闭")

# 创建全局串口管理器实例，指定使用 /dev/ttyHS1
serial_manager = SerialManager(port='/dev/ttyHS1', baudrate=9600)
