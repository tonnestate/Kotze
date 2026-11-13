#ifndef KOTZE_PROTOCOL_H
#define KOTZE_PROTOCOL_H
#include <stddef.h>
/* Read-only ASCII V1 request, one line per connection. The authenticated
 * work scope is supplied separately by the host, NEVER by the client. */
typedef enum { KP_OK=0, KP_BAD=-1, KP_DENIED=-2 } kp_status;
typedef enum { KP_ENTRY=1, KP_EDGES=2 } kp_operation;
typedef struct {
    kp_operation operation;
    char work_id[129],object_key[129],after_key[129];
    int direction; /* 1=OUT, 2=IN */
    unsigned limit;
} kp_request;
int kp_parse(const char *data,size_t length,const char *allowed_work,
             kp_request *out);
#endif
