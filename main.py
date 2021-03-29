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
listen_port = int(config_dict["listen_port"])

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
el_sw_pin.value(0)
head_sw_pin.value(1)             #obwód czujnika otwarcia głowicy zamknięty
##
#------------------------------------------------------------------------------------------------------------



#-------------------------------------------   ZMIENNE GLOBALNE   -------------------------------------------
last_led_pin_values = [led1_pin.value(), led2_pin.value(), led3_pin.value(), led4_pin.value()]       #poprzednie stany diod
reset_tslcp_times = [0,0,0,0]                                                                        #czasy w których zresetowano zmienne 'time_since_last_change_pins'
time_since_last_change_pins = [0,0,0,0]                                                              #czasy od ostatnich zmian stanów diod 
express_status = -1                                                                                  #status ekspresu -   -1 oznacza aktualizację danych o ekspresie
last_head_status = 0                                                                                 #poprzedni status głowicy
coffee_ready = 0                                                                                     #flaga gotowości kawy do odebrania
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

#uruchomienie webrepl na bieżącym adresie
import webrepl
webrepl.start()

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
s_server.bind(('', listen_port))
s_server.listen(5)
#------------------------------------------------------------------------------------------------------------



#-----------------------------------------------   FUNKCJE   ------------------------------------------------

#funkcja pobierająca i konwertująca dane z serwera domoticz
def send_data_to_HA(data):
    global server_ip, server_port
    
    try:
        url = 'http://' + server_ip + ':' + server_port + '/api/states/sensor.coffee_express'
        headers = {"Authorization": "Bearer " + api_token}
        #data = '{"state":"Robimy kawe ;)"}'
        
        res = urequests.post(url, headers=headers, data=data)     #wysłanie danych do serwera - POST
        res.close()
        print('Zaktualizowano dane na serwerze.')
        #print(res)
        print("Wysłano:  " + str(data))
    except:
        print("Błąd podczas wysyłania danych do HA")
        pass
            
            
            
#funkcja pobierająca czasy od ostatnich zmian stanów diod
def get_leds_time():
    global time_since_last_change_pins, reset_tslcp_times, last_led_pin_values, express_status
    
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
    global time_since_last_change_pins, reset_tslcp_times, last_led_pin_values, debug_msg
    
    #ekspres gotowy do pracy w trybia 'auto'
    if(led1_pin.value() == 0 and time_since_last_change_pins[0] > 2 and time_since_last_change_pins[1] > 2 and time_since_last_change_pins[2] > 2 and time_since_last_change_pins[3] > 2):
        #print("TRYB 1: Gotowy do pracy.")
        debug_msg = "TRYB 1: Gotowy do pracy."
        return 1
        
    #ekspres w trakcie pracy - tryb 'auto'
    elif(time_since_last_change_pins[0] < 2 and time_since_last_change_pins[1] > 2 and time_since_last_change_pins[2] > 2 and time_since_last_change_pins[3] > 2):
        #print("TRYB 2: Kawa w trakcie przygotowywania.")
        debug_msg = "TRYB 2: Kawa w trakcie przygotowywania."
        return 2
    
    #ekspres zakończył pracę - jest w trybie 'manual'
    elif(led2_pin.value() == 0 and time_since_last_change_pins[0] > 2 and time_since_last_change_pins[1] > 2 and time_since_last_change_pins[2] > 2 and time_since_last_change_pins[3] > 2):
        #print("TRYB 3: Kawa gotowa!")
        debug_msg = "TRYB 3: Kawa gotowa!"
        return 3
        
    #ekspres ma zagrzaną wodę ale nie ogarnia żeby się włączyć przyciskiem - trzeba zasymulować otwarcie i zamknięcie głowicy
    elif(led3_pin.value() == 0 and time_since_last_change_pins[0] > 2 and time_since_last_change_pins[1] > 2 and time_since_last_change_pins[2] > 2 and time_since_last_change_pins[3] > 2):
        #print("TRYB 4: Woda jest ciepła - otwórz i zamknij głowicę.")
        debug_msg = "TRYB 4: Woda jest ciepła - otwórz i zamknij głowicę."
        return 4
        
    #ekspres w trybie standby
    elif(time_since_last_change_pins[0] > 2 and time_since_last_change_pins[1] > 2 and time_since_last_change_pins[2] < 2 and time_since_last_change_pins[3] > 2):
        #print("TRYB 5: Grzanie wody.")
        debug_msg = "TRYB 5: Grzanie wody."
        return 5
        
    #ekspres w trybie standby
    elif(led4_pin.value() == 0 and time_since_last_change_pins[0] > 2 and time_since_last_change_pins[1] > 2 and time_since_last_change_pins[2] > 2 and time_since_last_change_pins[3] > 2):
        #print("TRYB 6: Standby")
        debug_msg = "TRYB 6: Standby"
        return 6
        
    #brak wody lub kapsułki
    elif(time_since_last_change_pins[0] < 2 and time_since_last_change_pins[1] < 2 and time_since_last_change_pins[2] < 2 and time_since_last_change_pins[3] < 2):
        #print("BŁĄD: Brak wody lub kapsułki.")
        debug_msg = "BŁĄD: Brak wody lub kapsułki."
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
    global last_head_status, coffee_ready
    
    current_head_status = head_open_sw_pin.value()
    if(last_head_status == 0 and current_head_status == 1):
        print('Otworzono głowice.')
        last_head_status = current_head_status
        
    elif(last_head_status == 1 and current_head_status == 0):
        print('Zamknięto głowice.')
        last_head_status = current_head_status
        coffee_ready = 0
        led.value(1)



#funkcja odpowiedzialna za robienie kawy
def make_coffee():
    global express_status
    
    #jeżeli odebrano poprzednio zrobioną kawę, wymieniono kapsułke i zamknięto głowicę
    if(coffee_ready == 0 and last_head_status == 0):
        print("Robimy kawę!!!")
        #status = get_express_status()
        
        if(express_status == 1):
            el_sw_pin.value(1)
            sleep(0.2)
            el_sw_pin.value(0)
            
        elif(express_status == 2 or express_status == 3 or express_status == 0):
            print("Nie można zrobić kawy: -kawa w trakcie przygotowania   -kawa gotowa   -brak wody lub kapsułki")
            return 0
        
        elif(express_status == 4):
            head_sw_pin.value(0)
            sleep(0.5)
            head_sw_pin.value(1)
            sleep(3)
            while((express_status != 1 and express_status != 4) or express_status == -1):
                print('Czekam..')
                print(express_status)
                #status = get_express_status()###########################
                sleep(0.1)
                
            print(express_status)    
            if(express_status == 1):
                sleep(3)
                el_sw_pin.value(1)
                sleep(0.2)
                el_sw_pin.value(0)
            elif(express_status == 4):
                sleep(3)
                head_sw_pin.value(0)
                sleep(0.5)
                head_sw_pin.value(1)
                
                sleep(5)
                el_sw_pin.value(1)
                sleep(0.2)
                el_sw_pin.value(0)
            
        elif(express_status == 5 or express_status == 6):
            el_sw_pin.value(1)
            sleep(0.2)
            el_sw_pin.value(0)
            sleep(3)
            while((express_status != 1 and express_status != 4) or express_status == -1):
                print('Czekam..')
                print(express_status)
                #status = get_express_status()###########################
                sleep(0.1)
                
            print(express_status)    
            if(express_status == 1):
                sleep(3)
                el_sw_pin.value(1)
                sleep(0.2)
                el_sw_pin.value(0)
            elif(express_status == 4):
                sleep(3)
                head_sw_pin.value(0)
                sleep(0.5)
                head_sw_pin.value(1)
                
                sleep(5)
                el_sw_pin.value(1)
                sleep(0.2)
                el_sw_pin.value(0)
    else:
        print("Poprzednia kawa nie została jeszcze odebrana!   lub   Głowica niezamknięta!")
        
#------------------------------------------------------------------------------------------------------------



#--------------------------------   WĄTEK OBSŁUGUJĄCY KOMUNIKACJE SIECIOWĄ   --------------------------------
def network_server_thread():
    print('Wątek wystartował!')
    
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
            make_coffee()
    
    


#------------------------------------------------------------------------------------------------------------


_thread.start_new_thread(network_server_thread, ())                   #uruchomienie wątku express_status_thread()


#----------------------------------------   GŁÓWNY WĄTEK PROGRAMU   -----------------------------------------

last_data_to_send = b'{"state":"status -1"}'                          #Ostatnio wysłane dane 
send_data_to_HA(last_data_to_send)                                    #wstępne wysłanie danych do serwera


while True:
    get_head_status()
    get_leds_time()
    express_status = get_express_status()                             #pobranie statusu ekspresu
    data_to_send = get_data_to_send_to_HA(express_status)             #przygotowanie danych do wysłania na podstawie statusu
    
    #jeżeli kawa została odebrana
    if(coffee_ready == 0):
        
        #jeżeli zmienił się status 
        if(last_data_to_send != data_to_send):
            print(debug_msg)
            print("")
            last_data_to_send = data_to_send
            
            #nie wysyłaj do serera statusu -1
            if(express_status != -1):                              
                send_data_to_HA(data_to_send)                          #wysłanie danych do serwera
                
                #jeżeli zrobiono kawę ustaw flagę gotowości kawy
                if(express_status == 3):
                    coffee_ready = 1
                    led.value(0)
#     print(led1_pin.value(), led2_pin.value(), led3_pin.value(), led4_pin.value())
    sleep(0.1)
#------------------------------------------------------------------------------------------------------------    
