from machine import Pin, PWM, deepsleep
import urequests
import network
import socket
import ujson
import gc
#import select
from time import sleep

gc.collect()

f = open("config.json", "r")
config_json = f.read()                         #pobranie danych konfiguracyjnych z pliku config.json
config_dict = ujson.loads(config_json)         #zdekodowanie danych json - zamiana na dictionary

f.close()
del config_json

#---------------------------------------   KONFIGURACJA URZĄDZENIA   ---------------------------------------
static_ip = config_dict["static_ip"]
mask_ip = config_dict["mask_ip"]
gate_ip = config_dict["gate_ip"]
dns_ip = config_dict["dns_ip"]
ssid = config_dict["ssid"]
password = config_dict["password"]

server_ip = config_dict["server_ip"]
server_port = config_dict["server_port"]

api_token = config_dict["api_token"]

#device1_idx = config_dict["device1_idx"]
#device2_idx = config_dict["device2_idx"]

#relay1_pin = int(config_dict["relay1_pin"])
#relay2_pin = int(config_dict["relay2_pin"])

#request_period = float(config_dict["request_period"])
#relay_pins_invert = config_dict["relay_pins_invert"]
cmd_start = config_dict["cmd_start"]
#cmd_off = config_dict["cmd_off"]

del config_dict
#------------------------------------------------------------------------------------------------------------



#-------------------------------------------   ZMIENNE GLOBALNE   -------------------------------------------

#------------------------------------------------------------------------------------------------------------



#------------------------------------------   KONFIGURACJA PINÓW   ------------------------------------------
led = Pin(2, Pin.OUT)    #wbudowana dioda led

#relay1 = Pin(relay1_pin, Pin.OUT)    #przekaźnik 1
#relay2 = Pin(relay2_pin, Pin.OUT)    #przekaźnik 2


#wyłączenie przekaźników
# if(relay_pins_invert == "False"):
#     relay1.value(0)
#     relay2.value(0)
# else:
#     relay1.value(1)
#    relay2.value(1)

#------------------------------------------------------------------------------------------------------------



#-----------------------------------   KONFIGURACJA POŁĄCZEŃ SIECIOWYCH   -----------------------------------
#utworzenie socketu do komunikacji - client
#s_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

#inicjalizacja WLAN
wlan = network.WLAN(network.STA_IF)

wlan.active(True)
wlan.ifconfig((static_ip, mask_ip, gate_ip, dns_ip))
wlan.connect(ssid, password)
#------------------------------------------------------------------------------------------------------------



#-----------------------------------------   PODŁĄCZENIE DO SIECI   -----------------------------------------
#oczekiwanie na podłączenie urządzenia Wi-Fi
print("Oczekiwanie na podłączenie do sieci Wi-Fi")

while wlan.isconnected() == False:
    led.value(1)
    sleep(0.2)
    led.value(0)
    sleep(0.2)
    print(".", end =" ")
    
print("")
print("Połączenie udane")
print("Konfigurajca Wi-Fi:  ", end =" ")
print(wlan.ifconfig())

#sygnalizacja podłączenia do sieci - LED
led.value(1)
sleep(2)
led.value(0)
for i in range(5):
    led.value(1)
    sleep(0.1)
    led.value(0)
    sleep(0.1)

#nasłuchiwanie na porcie 9000 
s_server.bind(('', 9000))
s_server.listen(5)
#------------------------------------------------------------------------------------------------------------



#-----------------------------------------------   FUNKCJE   ------------------------------------------------

#funkcja pobierająca i konwertująca dane z serwera domoticz
def send_data_to_HA():
    global server_ip, server_port
    
    url = 'http://' + server_ip + ':' + server_port + '/api/states/sensor.ekspres_do_kawy'
    headers = {"Authorization": "Bearer " + api_token}
    data = '{"state":"Robimy kawe ;)"}'
    
    response = urequests.post(url, headers=headers, data=data)     #wysłanie danych do serwera - POST
    print(response)

#------------------------------------------------------------------------------------------------------------






#----------------------------------------   GŁÓWNA PĘTLA PROGRAMU   -----------------------------------------
while True:
    conn, addr = s_server.accept()
    print('Odebrano połączenie z %s' % str(addr))
    request = conn.recv(1024)
    conn.send('HTTP/1.1 200 OK\n')
    conn.send('Content-Type: text/html\n')
    conn.send('Connection: close\n\n')
    conn.close()
    #print('Wiadomość = %s' % str(request))
    
    if(str(request).find(cmd_start) != -1):
        print("robimy kawe")
        send_data_to_HA()
#------------------------------------------------------------------------------------------------------------    
