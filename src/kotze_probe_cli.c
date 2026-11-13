#include "kotze_probe.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv){
    if(argc!=4){
        fputs("Usage: kotze-probe WORKSPACE git-status|git-diff-names TIMEOUT_MS\n",stderr);
        return 2;
    }
    errno=0;char *end=NULL;
    unsigned long ms=strtoul(argv[3],&end,10);
    if(errno||end==argv[3]||*end||ms<100||ms>60000)return 2;
    kpr_result result;
    int status=kpr_run(argv[1],argv[2],(unsigned)ms,KPR_MAX_OUTPUT,&result);
    printf("KPR1 status=%d exit=%d signal=%d elapsed_ms=%llu bytes=%zu\n",
           status,result.exit_code,result.term_signal,
           (unsigned long long)result.elapsed_ms,result.used);
    static const char chars[]="0123456789ABCDEF";
    for(size_t i=0;i<result.used;i++){
        unsigned char c=(unsigned char)result.data[i];
        putchar(chars[c>>4]);putchar(chars[c&15]);
    }
    putchar('\n');
    return status==KPR_OK&&result.exit_code==0?0:1;
}
