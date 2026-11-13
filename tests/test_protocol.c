#include "kotze_protocol.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define P(s,scope,out) kp_parse((s),strlen(s),(scope),(out))
int main(void){
    kp_request r={0};
    assert(P("V1 GET work-01 src/a.c\n","work-01",&r)==KP_OK);
    assert(r.operation==KP_ENTRY&&!strcmp(r.object_key,"src/a.c"));
    assert(P("V1 EDGES work-01 symbol:fn OUT - 4\n","work-01",&r)==KP_OK);
    assert(r.operation==KP_EDGES&&r.direction==1&&r.limit==4);
    assert(P("V1 EDGES work-01 symbol:fn IN src/f 64\n","work-01",&r)==KP_OK);
    assert(r.direction==2&&!strcmp(r.after_key,"src/f"));
    assert(P("V1 GET other-work x\n","work-01",&r)==KP_DENIED);
    assert(P("V1 DELETE work-01 x\n","work-01",&r)==KP_BAD);
    assert(P("V1 GET work-01 x extra\n","work-01",&r)==KP_BAD);
    assert(P("V1 GET work-01 x;cat\n","work-01",&r)==KP_BAD);
    assert(P("V1 EDGES work-01 x OUT - 65\n","work-01",&r)==KP_BAD);
    assert(P("V1 EDGES work-01 x OUT - 0\n","work-01",&r)==KP_BAD);
    assert(P("V1 EDGES work-01 x OUT - -1\n","work-01",&r)==KP_BAD);
    assert(P("V1 EDGES work-01 x OUT - 4 trailing\n","work-01",&r)==KP_BAD);
    assert(P("V1 GET work-01 x\r\n","work-01",&r)==KP_BAD);
    assert(P("V1 GET work-01 x\nV1 GET work-01 y\n","work-01",&r)==KP_BAD);
    const char nul[]={'V','1',' ','G','E','T',' ','w','o','r','k','-','0','1',
                      ' ','x','\0','\n'};
    assert(kp_parse(nul,sizeof(nul),"work-01",&r)==KP_BAD);
    puts("PASS: scoped read-only protocol parsing and rejection");
    return 0;
}
