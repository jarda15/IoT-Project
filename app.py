import tkinter as tk
import paho.mqtt.client as mqtt
import json
import winsound
import csv
from datetime import datetime

class GrilApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MasterChef Dashboard PRO")
        self.root.geometry("450x600")
        self.root.configure(bg='#121212') 
        
        self.target_maso = tk.DoubleVar(value=75.0)
        self.target_gril = tk.DoubleVar(value=200.0)
        self.last_t_maso = 0.0
        self.last_t_gril = 0.0
        
        self.was_maso_ok = None
        self.was_gril_ok = None

        # GUI
        tk.Label(root, text="TEPLOTA MÄSA", font=("Arial", 10, "bold"), bg="#0F0F11", fg="gray").pack(pady=(20, 0))
        self.label_maso = tk.Label(root, text="--.-°", font=("Arial", 60, "bold"), bg="#0F0F11", fg="#00bbff")
        self.label_maso.pack()
        tk.Scale(root, from_=40, to=100, orient="horizontal", variable=self.target_maso).pack(fill="x", padx=60)

        tk.Label(root, text="TEPLOTA V GRILE", font=("Arial", 10, "bold"), bg="#0F0F11", fg="gray").pack(pady=(30, 0))
        self.label_gril = tk.Label(root, text="--.-°", font=("Arial", 60, "bold"), bg="#0F0F11", fg="#ffffff")
        self.label_gril.pack()
        tk.Scale(root, from_=100, to=300, orient="horizontal", variable=self.target_gril).pack(fill="x", padx=60)

        self.status_bar = tk.Label(root, text="Status: Odpojené", bg="#0F0F11", fg="red")
        self.status_bar.pack(side="bottom", pady=20)

        self.setup_mqtt()

    def sound_ok(self):
        #right temp
        winsound.Beep(1000, 300)

    def sound_error(self):
        #offlimit
        for _ in range(3):
            winsound.Beep(1500, 100)

    def save_to_csv(self, m, g):
        #excel
        try:
            with open('data_gril_export.csv', mode='a', newline='') as f:
                writer = csv.writer(f)
                
                writer.writerow([datetime.now().strftime("%H:%M:%S"), m, g])
        except Exception as e:
            print(f"Chyba pri zápise do CSV: {e}")

    def setup_mqtt(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        try:
            self.client.connect_async("broker.hivemq.com", 1883, 60)
            self.client.loop_start()
        except:
            self.status_bar.config(text="Status: Chyba siete", fg="red")
# connect to broker
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.status_bar.config(text="Status: Online", fg="#00ff00")
            self.client.subscribe("iot/masterchef/data")
        else:
            self.status_bar.config(text="Status: Chyba pripojenia", fg="red")

    def on_disconnect(self, client, userdata, rc):
        self.status_bar.config(text="Status: Odpojené", fg="red")
#data
    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            self.last_t_maso = float(data.get('maso', 0))
            self.last_t_gril = float(data.get('gril', 0))
            
            self.label_maso.config(text=f"{self.last_t_maso:.1f}°")
            self.label_gril.config(text=f"{self.last_t_gril:.1f}°")
            
            #save to csv
            self.save_to_csv(self.last_t_maso, self.last_t_gril)
            
            self.check_alarms()
        except: pass

    def check_alarms(self):
        limit_m = self.target_maso.get()
        limit_g = self.target_gril.get()

        #meat
        is_maso_currently_ok = (limit_m <= self.last_t_maso <= (limit_m + 3))
        if self.was_maso_ok is not None:
            if is_maso_currently_ok != self.was_maso_ok:
                if is_maso_currently_ok: self.sound_ok()
                else: self.sound_error()
        self.was_maso_ok = is_maso_currently_ok
        
        if is_maso_currently_ok: self.label_maso.config(fg="#00ff00")
        elif self.last_t_maso > (limit_m + 3): self.label_maso.config(fg="#ff4444")
        else: self.label_maso.config(fg="#00bbff")

        #grill
        is_gril_currently_ok = ((limit_g - 10) <= self.last_t_gril <= (limit_g + 10))
        if self.was_gril_ok is not None:
            if is_gril_currently_ok != self.was_gril_ok:
                if is_gril_currently_ok: self.sound_ok()
                else: self.sound_error()
        self.was_gril_ok = is_gril_currently_ok

        if is_gril_currently_ok: self.label_gril.config(fg="#00ff00")
        elif self.last_t_gril > (limit_g + 10): self.label_gril.config(fg="#ff4444")
        else: self.label_gril.config(fg="#ffffff")

if __name__ == "__main__":
    root = tk.Tk()
    app = GrilApp(root)
    root.mainloop()