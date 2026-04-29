import tkinter as tk
import paho.mqtt.client as mqtt
import json
import csv
from datetime import datetime
import os 
import platform

# --- ZVUK ---
def make_beep(freq, duration, count=1):
    if platform.system() == "Windows":
        try:
            import winsound
            for _ in range(count): winsound.Beep(freq, duration)
        except: pass
    else:
        for _ in range(count):
            os.system(f"play -n synth {duration/1000} sin {freq} > /dev/null 2>&1")

class GrilApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MasterChef Dashboard PRO")
        self.root.geometry("450x650")
        self.root.configure(bg='#121212') 
        
        self.target_maso = tk.DoubleVar(value=75.0)
        self.target_gril = tk.DoubleVar(value=200.0)
        self.last_t_maso = 0.0
        self.last_t_gril = 0.0
        
        self.was_maso_ok = None
        self.was_gril_ok = None

        # --- GUI MÄSO ---
        tk.Label(root, text="TEPLOTA MÄSA", font=("Arial", 10, "bold"), bg="#121212", fg="gray").pack(pady=(20, 0))
        self.label_maso = tk.Label(root, text="--.-°", font=("Arial", 60, "bold"), bg="#121212", fg="#00bbff")
        self.label_maso.pack()
        self.slider_maso = tk.Scale(root, from_=0, to=100, orient="horizontal", variable=self.target_maso, bg="#121212", fg="white", highlightthickness=0)
        self.slider_maso.pack(fill="x", padx=60)

        # --- GUI GRIL ---
        tk.Label(root, text="TEPLOTA V GRILE", font=("Arial", 10, "bold"), bg="#121212", fg="gray").pack(pady=(30, 0))
        self.label_gril = tk.Label(root, text="--.-°", font=("Arial", 60, "bold"), bg="#121212", fg="#ffffff")
        self.label_gril.pack()
        self.slider_gril = tk.Scale(root, from_=0, to=200, orient="horizontal", variable=self.target_gril, bg="#121212", fg="white", highlightthickness=0)
        self.slider_gril.pack(fill="x", padx=60)

        # --- CONFIRMATION BUTTON ---
        self.btn_send = tk.Button(root, text="ODOSLAŤ NASTAVENIA", font=("Arial", 12, "bold"), 
                                  bg="#00ff00", fg="black", activebackground="#00cc00",
                                  command=self.publish_all_settings, cursor="hand2")
        self.btn_send.pack(pady=30, padx=60, fill="x")

        self.status_bar = tk.Label(root, text="Status: Odpojené", bg="#121212", fg="red")
        self.status_bar.pack(side="bottom", pady=20)

        self.setup_mqtt()

    def publish_all_settings(self):
        """Odošle obe cieľové teploty naraz po stlačení tlačidla."""
        if not self.client.is_connected():
            print("Chyba: MQTT nie je pripojené!")
            return

        val_m = float(self.target_maso.get())
        val_g = float(self.target_gril.get())

        self.client.publish("IoTProject/9/grill/Tmaso", json.dumps({"masoTarget": val_m}))
        self.client.publish("IoTProject/9/grill/Tgrill", json.dumps({"grillTarget": val_g}))

        print(f"Odoslané: Mäso {val_m}°, Gril {val_g}°")
        
        original_text = self.btn_send.cget("text")
        self.btn_send.config(text="ODOSLANÉ!", bg="white")
        self.root.after(1000, lambda: self.btn_send.config(text=original_text, bg="#00ff00"))

    def sound_ok(self): make_beep(1000, 300, 1)
    def sound_error(self): make_beep(1500, 100, 3)

    def save_to_csv(self, m, g):
        try:
            with open('data_gril_export.csv', mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([datetime.now().strftime("%H:%M:%S"), m, g])
        except: pass

    def setup_mqtt(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        try:
            self.client.connect_async("147.229.148.105", 11883, 60)
            self.client.loop_start()
        except:
            self.status_bar.config(text="Status: Chyba siete", fg="red")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.status_bar.config(text="Status: Online", fg="#00ff00")
            self.client.subscribe("IoTProject/9/grill/teplota")
        else:
            self.status_bar.config(text=f"Status: Chyba ({rc})", fg="red")

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            self.last_t_maso = float(data.get('maso', 0))
            self.last_t_gril = float(data.get('gril', 0))
            
            self.label_maso.config(text=f"{self.last_t_maso:.1f}°")
            self.label_gril.config(text=f"{self.last_t_gril:.1f}°")
            
            self.save_to_csv(self.last_t_maso, self.last_t_gril)
            self.check_alarms()
        except Exception as e:
            print(f"Chyba dát: {e}")

    def check_alarms(self):
        limit_m = self.target_maso.get()
        limit_g = self.target_gril.get()
        tolerancia = 5.0

        maso_ok = (limit_m - tolerancia <= self.last_t_maso <= limit_m + tolerancia)
        if self.was_maso_ok is not None and maso_ok != self.was_maso_ok:
            if maso_ok: self.sound_ok()
            else: self.sound_error()
        self.was_maso_ok = maso_ok
        
        gril_ok = (limit_g - tolerancia <= self.last_t_gril <= limit_g + tolerancia)
        if self.was_gril_ok is not None and gril_ok != self.was_gril_ok:
            if gril_ok: self.sound_ok()
            else: self.sound_error()
        self.was_gril_ok = gril_ok

        self.label_maso.config(fg="#00ff00" if maso_ok else ("#ff4444" if self.last_t_maso > limit_m + tolerancia else "#00bbff"))
        self.label_gril.config(fg="#00ff00" if gril_ok else ("#ff4444" if self.last_t_gril > limit_g + tolerancia else "#ffffff"))

if __name__ == "__main__":
    root = tk.Tk()
    app = GrilApp(root)
    root.mainloop()
