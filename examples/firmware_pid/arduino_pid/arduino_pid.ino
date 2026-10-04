// XiLoop HiL firmware for Arduino-compatible boards (Uno, Nano, ESP32, RP2040, ...).
// The control law is the same pid_core.c that runs on the host - copy pid_core.h and
// pid_core.c next to this sketch. Then in Studio: Device -> Board over serial, pick the
// COM port, 115200 baud.

extern "C" {
#include "pid_core.h"
}

pid_t_ pid;
char line[96];
int len = 0;

void setup() {
  Serial.begin(115200);
  pid_init(&pid);
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c != '\n') { if (len < (int)sizeof(line) - 1) line[len++] = c; continue; }
    line[len] = 0;
    len = 0;
    char reply[48];
    xiloop_handle_line(&pid, line, reply, sizeof(reply));
    Serial.println(reply);
  }
}
