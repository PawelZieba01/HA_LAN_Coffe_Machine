from machine import Pin
import urequests
import network
import socket
import ujson
import gc
import _thread
from time import sleep, time

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

cmd_start = config_dict["cmd_start"]

del config_dict
#------------------------------------------------------------------------------------------------------------




#------------------------------------------   KONFIGURACJA PINÓW   ------------------------------------------
led = Pin(2, Pin.OUT)    #wbudowana dioda led

#piny czytające stany diod led
led1_pin = Pin(34, Pin.IN)
led2_pin = Pin(35, Pin.IN)
led3_pin = Pin(33, Pin.IN)
led4_pin = Pin(32, Pin.IN)

head_open_sw_pin = Pin(25, Pin.IN)    #czujnik otwarcia głowicy

head_sw_pin = Pin(4, Pin.OUT)    #wyjście rozłączające styk zamknięcia głowicy, 0 - obwód otwarty, 1 - obwód zamkniety
el_sw_pin = Pin(26, Pin.OUT)     #wyjście załączające ekspres


##
head_sw_pin.value(1)             #obwód czujnika otwarcia głowicy zamknięty
##
#------------------------------------------------------------------------------------------------------------



#-------------------------------------------   ZMIENNE GLOBALNE   -------------------------------------------
last_led_pin_values = [led1_pin.value(), led2_pin.value(), led3_pin.value(), led4_pin.value()]       #poprzedni stan diod
reset_tslcp_times = [0,0,0,0]                                                                        #czasy w których zresetowano zmienne 'time_since_last_change_pins'
time_since_last_change_pins = [0,0,0,0]
#------------------------------------------------------------------------------------------------------------



#-----------------------------------   KONFIGURACJA POŁĄCZEŃ SIECIOWYCH   -----------------------------------
#utworzenie socketu do komunikacji - client
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
def send_data_to_HA(data):
    global server_ip, server_port
    
    url = 'http://' + server_ip + ':' + server_port + '/api/states/sensor.ekspres_do_kawy'
    headers = {"Authorization": "Bearer " + api_token}
    #data = '{"state":"Robimy kawe ;)"}'
    
    res = urequests.post(url, headers=headers, data=data)     #wysłanie danych do serwera - POST
    res.close()
    print(res)
    print(data)
            
            
            
            
#funkcja pobierająca czasy od ostatnich zmian stanów diod
def get_leds_time():
    global time_since_last_change_pins, reset_tslcp_times, last_led_pin_values
    
    current_pin_values = [led1_pin.value(), led2_pin.value(), led3_pin.value(), led4_pin.value()]
    for i in range(4):
        time_since_last_change_pins[i] = time() - reset_tslcp_times[i]

        if(last_led_pin_values[i] != current_pin_values[i]):
            #print("zmiana stanu" + str(i))
            last_led_pin_values[i] = current_pin_values[i]
            reset_tslcp_times[i] = time()
            time_since_last_change_pins[i] = 0




#funkcja pobierająca informacje w jakim trybie jest ekspres
def get_express_status():
    global time_since_last_change_pins, reset_tslcp_times, last_led_pin_values
    
    #ekspres gotowy do pracy w trybia 'auto'
    if(led1_pin.value() == 0 and time_since_last_change_pins[0] > 2 and time_since_last_change_pins[1] > 2 and time_since_last_change_pins[2] > 2 and time_since_last_change_pins[3] > 2):
        print("TRYB 1: gotowy do pracy")
        return 1
        
    #ekspres w trakcie pracy - tryb 'auto'
    elif(time_since_last_change_pins[0] < 2 and time_since_last_change_pins[1] > 2 and time_since_last_change_pins[2] > 2 and time_since_last_change_pins[3] > 2):
        print("TRYB 2: kawa w trakcie przygotowywania")
        return 2
    
    #ekspres zakończył pracę - jest w trybie 'manual'
    elif(led2_pin.value() == 0 and time_since_last_change_pins[0] > 2 and time_since_last_change_pins[1] > 2 and time_since_last_change_pins[2] > 2 and time_since_last_change_pins[3] > 2):
        print("TRYB 3: kawa gotowa!")
        return 3
        
    #ekspres ma zagrzaną wodę ale nie ogarnia żeby się włączyć przyciskiem - trzeba zasymulować otwarcie i zamknięcie głowicy
    elif(led3_pin.value() == 0 and time_since_last_change_pins[0] > 2 and time_since_last_change_pins[1] > 2 and time_since_last_change_pins[2] > 2 and time_since_last_change_pins[3] > 2):
        print("TRYB 4: woda jest ciepła - otwórz i zamknij głowicę")
        return 4
        
    #ekspres w trybie standby
    elif(time_since_last_change_pins[0] > 2 and time_since_last_change_pins[1] > 2 and time_since_last_change_pins[2] < 2 and time_since_last_change_pins[3] > 2):
        print("TRYB 5: grzanie wody")
        return 5
        
    #ekspres w trybie standby
    elif(led4_pin.value() == 0 and time_since_last_change_pins[0] > 2 and time_since_last_change_pins[1] > 2 and time_since_last_change_pins[2] > 2 and time_since_last_change_pins[3] > 2):
        print("TRYB 6: standby")
        return 6
        
    #brak wody lub kapsułki
    elif(time_since_last_change_pins[0] < 2 and time_since_last_change_pins[1] < 2 and time_since_last_change_pins[2] < 2 and time_since_last_change_pins[3] < 2):
        print("BŁĄD: brak wody lub kapsułki")
        return 0
    else:
        return -1


#funkcja zwracająca dane do wyświetlenia na interfejsie graficznym w zależności od statusu ekspresu
def get_data_to_send_to_HA(status):
    
    if(status == 0):
        data = b'{"state":"Brak wody lub kapsułki :( "}'
    elif(status == 1 or status == 4 or status == 6):
        data = b'{"state":"Kawy? "}'
    elif (status == 2):
        data = b'{"state":"Robimy kawę!!!"}'
    elif (status == 3):
        data = b'{"state":"Kawa gotowa!!!"}'
    elif(status == 5):
        data = b'{"state":"Grzejemy wode ;)"}'
    else:
        data = data = b'{"state":"status -1"}'
    
    return data
    
    


#funkcja sprawdzająca czy głowica została otwarta i zamknięta, 0 - zamknięta, 1 - otwarta
def get_head_status():
    global last_head_status
    
    current_head_status = head_open_sw_pin.value()
    if(last_head_status == 0 and current_head_status == 1):
        print('otworzono głowice')
        last_head_status = current_head_status
        
    elif(last_head_status == 1 and current_head_status == 0):
        print('zamknięto głowice')
        last_head_status = current_head_status



#funkcja odpowiedzialna za robienie kawy
def make_coffee():
    status = get_express_status()
    
    if(status == 1):
        el_sw_pin.value(1)
        sleep(0.2)
        el_sw_pin.value(0)
        
    elif(status == 2 or status == 3 or status == 0):
        return 0
    
    elif(status == 4):
        
        head_sw_pin.value(0)
        sleep(0.5)
        head_sw_pin.value(1)
        
        sleep(4)
        el_sw_pin.value(1)
        sleep(0.2)
        el_sw_pin.value(0)
        
    elif(status == 5):
        el_sw_pin.value(1)
        sleep(0.2)
        el_sw_pin.value(0)
        while(status != 1 and status != 4):
            print('czekam')
            status = get_express_status()###########################
            sleep(0.1)
            
        if(status == 1):
            el_sw_pin.value(1)
            sleep(0.2)
            el_sw_pin.value(0)
        elif(status == 4):
            head_sw_pin.value(0)
            sleep(0.5)
            head_sw_pin.value(1)
            
            sleep(5)
            el_sw_pin.value(1)
            sleep(0.2)
            el_sw_pin.value(0)
            
    elif(status == 6):
        el_sw_pin.value(1)
        sleep(0.2)
        el_sw_pin.value(0)
        while(status != 1 and status != 4):
            print('czekam')
            status = get_express_status()#################################
            sleep(0.1)
            
        if(status == 1):
            el_sw_pin.value(1)
            sleep(0.2)
            el_sw_pin.value(0)
        elif(status == 4):
            head_sw_pin.value(0)
            sleep(0.5)
            head_sw_pin.value(1)
            
            sleep(5)
            el_sw_pin.value(1)
            sleep(0.2)
            el_sw_pin.value(0)
        
#------------------------------------------------------------------------------------------------------------



#--------------------------------   WĄTEK OBSŁUGUJĄCY POBIERANIE I AKTUALIZACJĘ INFORMACJI O EKSPRESIE   --------------------------------
def express_status_thread():
    print('wątek wystartował!')
    
    #wątek obsługujący komunikację sieciową
    while True:
        conn, addr = s_server.accept()
        print('Odebrano połączenie z %s' % str(addr))
        request = conn.recv(1024)
        conn.send('HTTP/1.1 200 OK\n')
        conn.send('Content-Type: text/html\n')
        conn.send('Connection: close\n\n')
        conn.close()
        #print('Wiadomość = %s' % str(request))

        #jeśli odebrano rozkaz robienia kawy
        if(str(request).find(cmd_start) != -1):
            print("robimy kawe")
            make_coffee()
    
    


#------------------------------------------------------------------------------------------------------------



#----------------------------------------   GŁÓWNA PĘTLA PROGRAMU   -----------------------------------------
_thread.start_new_thread(express_status_thread, ())       #uruchomienie wątku express_status_thread()

last_data_to_send = b'{"state":"Kawy? "}'
send_data_to_HA(last_data_to_send)             #wstępne wysłanie danych do serwera
express_status = 0


while True:
    get_leds_time()
    express_status = get_express_status()                          #pobranie statusu ekspresu
    data_to_send = get_data_to_send_to_HA(express_status)          #przygotowanie danych do wysłania na podstawie statusu
    
    print(data_to_send)
    #jeżeli zmienił się status i poprawnie go odczytano 
    if(last_data_to_send != data_to_send and express_status != -1):
        last_data_to_send = data_to_send
        send_data_to_HA(data_to_send)                              #wysłanie danych do serwera
    
    sleep(0.1)
#------------------------------------------------------------------------------------------------------------    
