/* Host shim: run pid_core as a TCP server on port 5555 (PiL on your PC).
 *
 *   Windows (MSVC):  cl /O2 /D_CRT_SECURE_NO_WARNINGS host_main.c pid_core.c ws2_32.lib /Fe:pid_firmware.exe
 *   Linux / macOS:   cc -O2 host_main.c pid_core.c -o pid_firmware
 *
 * Then point a SocketDevice (or Studio: Device -> Firmware over TCP) at 127.0.0.1:5555.
 */
#include "pid_core.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <winsock2.h>
typedef SOCKET sock_t;
#define CLOSE closesocket
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int sock_t;
#define CLOSE close
#endif

int main(int argc, char **argv)
{
    int port = argc > 1 ? atoi(argv[1]) : 5555, one = 1;
    struct sockaddr_in addr = {0};
    sock_t srv, cli;
#ifdef _WIN32
    WSADATA w;
    WSAStartup(MAKEWORD(2, 2), &w);
#endif
    srv = socket(AF_INET, SOCK_STREAM, 0);
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, (const char *)&one, sizeof one);
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons((unsigned short)port);
    if (bind(srv, (struct sockaddr *)&addr, sizeof addr) || listen(srv, 1)) {
        fprintf(stderr, "cannot listen on port %d\n", port);
        return 1;
    }
    printf("pid_firmware listening on 127.0.0.1:%d\n", port);
    fflush(stdout);

    for (;;) {                                   /* one host at a time, forever */
        pid_t_ pid;
        char line[128], reply[64], c;
        int len = 0;
        cli = accept(srv, NULL, NULL);
        setsockopt(cli, IPPROTO_TCP, TCP_NODELAY, (const char *)&one, sizeof one);
        pid_init(&pid);
        while (recv(cli, &c, 1, 0) == 1) {
            if (c == '\r') continue;
            if (c != '\n') { if (len < (int)sizeof line - 1) line[len++] = c; continue; }
            line[len] = 0;
            len = 0;
            xiloop_handle_line(&pid, line, reply, sizeof reply - 1);
            {
                int r = (int)strlen(reply);
                reply[r] = '\n';
                send(cli, reply, r + 1, 0);
            }
        }
        CLOSE(cli);
    }
}
