#include "pid_core.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void pid_init(pid_t_ *p)
{
    p->kp = 2.0f; p->ki = 1.0f; p->kd = 0.05f; p->out_max = 10.0f;
    p->integ = p->prev_err = p->setpoint = 0.0f;
}

float pid_update(pid_t_ *p, float meas, float dt)
{
    float err = p->setpoint - meas;
    float deriv = dt > 0 ? (err - p->prev_err) / dt : 0.0f;
    float out;
    p->integ += err * dt;
    p->prev_err = err;
    out = p->kp * err + p->ki * p->integ + p->kd * deriv;
    if (out > p->out_max || out < -p->out_max) {
        p->integ -= err * dt;                       /* anti-windup */
        out = out > 0 ? p->out_max : -p->out_max;
    }
    return out;
}

void xiloop_handle_line(pid_t_ *p, const char *line, char *out, int n)
{
    char name[16];
    float a, b;

    switch (line[0]) {
    case 'T':
        if (sscanf(line + 1, "%f %f", &a, &b) == 2) {
            snprintf(out, n, "%.7g", pid_update(p, a, b));
            return;
        }
        break;
    case 'S':
        if (sscanf(line + 1, "%f", &a) == 1) { p->setpoint = a; snprintf(out, n, "OK"); return; }
        break;
    case 'R':
        p->integ = p->prev_err = 0.0f;
        snprintf(out, n, "OK");
        return;
    case 'P':
        if (sscanf(line + 1, "%15s %f", name, &a) == 2) {
            float *f = !strcmp(name, "kp") ? &p->kp : !strcmp(name, "ki") ? &p->ki
                     : !strcmp(name, "kd") ? &p->kd : !strcmp(name, "out_max") ? &p->out_max : 0;
            if (f) { *f = a; snprintf(out, n, "OK"); return; }
            snprintf(out, n, "ERR unknown parameter %s", name);
            return;
        }
        break;
    }
    snprintf(out, n, "ERR malformed");
}
