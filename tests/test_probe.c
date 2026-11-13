#include "kotze_probe.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
int main(void){
    kpr_result r;
    assert(kpr_run("/tmp","sh",1000,1024,&r)==KPR_DENIED);
    assert(kpr_run("relative","git-status",1000,1024,&r)==KPR_DENIED);
    assert(kpr_run("/tmp","git-status",99,1024,&r)==KPR_DENIED);
    assert(kpr_run("/tmp","git-status",1000,KPR_MAX_OUTPUT+1,&r)==KPR_DENIED);
    assert(kpr_run("/tmp","git-status",1000,1024,NULL)==KPR_DENIED);
    if(geteuid()!=0&&access("/usr/bin/git",X_OK)==0){
        char path[]="/tmp/kotze_probe_XXXXXX";
        assert(mkdtemp(path)!=NULL);
        int rc=kpr_run(path,"git-status",5000,1024,&r);
        assert(rc==KPR_OK||rc==KPR_DENIED);
        if(rc==KPR_OK)assert(r.exit_code!=0&&r.used>0);
        assert(rmdir(path)==0);
    }
    puts("PASS: fixed Git diagnostic admission and bounded process result");
    return 0;
}
