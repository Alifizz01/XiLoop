/* XiLoop firmware example - the portable part.
 *
 * pid_core.{h,c} is plain C99 with no I/O: the same files build for the host
 * (PiL over TCP), for Renode/QEMU, and for a real MCU (HiL over UART).
 * xiloop_handle_line() implements the whole XiLoop line protocol:
 *
 *   R                 -> OK        reset
 *   S <setpoint>      -> OK        new target
 *   P <name> <value>  -> OK|ERR    kp, ki, kd, out_max
 *   T <meas> <dt>     -> <command> one control tick
 */
#ifndef PID_CORE_H
#define PID_CORE_H

typedef struct {
    float kp, ki, kd, out_max;
    float integ, prev_err, setpoint;
} pid_t_;

void pid_init(pid_t_ *p);
float pid_update(pid_t_ *p, float measurement, float dt);

/* Parse one request line (no newline) and write the reply into out[n]. */
void xiloop_handle_line(pid_t_ *p, const char *line, char *out, int n);

#endif
