#include "kotze.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>

static const char *optional(const char *s) { return !strcmp(s,"-") ? NULL : s; }
static int number(const char *text,int *out){
    char *end=NULL;errno=0;
    long n=strtol(text,&end,10);
    if(errno||!text[0]||*end||n<0||n>INT_MAX)return 0;
    *out=(int)n;return 1;
}
static int64_t revision(const char *text,int *ok){
    char *end=NULL;errno=0;
    long long n=strtoll(text,&end,10);
    *ok=!(errno||!text[0]||*end||n<0);
    return (int64_t)n;
}
static int role(const char *s,kotze_role *r){
    if(!strcmp(s,"OWNER"))*r=KOTZE_OWNER;
    else if(!strcmp(s,"CONTROLLER"))*r=KOTZE_CONTROLLER;
    else if(!strcmp(s,"WORKER"))*r=KOTZE_WORKER;
    else if(!strcmp(s,"VERIFIER"))*r=KOTZE_VERIFIER;
    else return 0;
    return 1;
}
static int usage(void){
    fputs("KOTZE Harness C11 control kernel (intent only; does not execute tools)\n"
          "Usage: kotze-core DB COMMAND ...\n"
          " create ID REQ_DIGEST ORIGINAL_REQUEST BASE_SHA CONTRACT_HASH CONTRACT_TEXT MODE DELIVERY_REQUIRED BUDGET\n"
          " status WORK_ID\n"
          " event WORK_ID EVENT_ID EVENT ACTOR EVIDENCE CANDIDATE_SHA ORACLE_HASH CONTRACT_HASH REVISION\n"
          " option-add WORK_ID OPTION_ID ORDINAL HYPOTHESIS\n"
          " option-decide WORK_ID OPTION_ID REFUTED|SUPPORTED|INAPPLICABLE EVIDENCE\n"
          " option-next WORK_ID\n"
          " action-reserve WORK_ID ACTION_ID READ|MODEL|TEST|WRITE|NETWORK FINGERPRINT ENV_DIGEST OWNER_APPROVED\n"
          " action-finish ACTION_ID OUTCOME_DIGEST\n"
          " success-add WORK_ID CAPABILITY ENV_DIGEST RECEIPT\n"
          " success-find CAPABILITY ENV_DIGEST\n"
          "Use '-' for absent optional event fields. This CLI is a trusted local demo,\n"
          "not an untrusted-worker security boundary. Do not expose it over the network.\n",stderr);
    return 2;
}
int main(int argc,char **argv){
    if(argc<4)return usage();
    kotze_t *k=NULL;
    if(kotze_open(&k,argv[1])!=KOTZE_OK){fputs("Cannot open local SQLite database\n",stderr);return 1;}
    const char *cmd=argv[2];int rc=KOTZE_DENIED,ok=1;
    if(!strcmp(cmd,"create")&&argc==12){
        int delivery=0,budget=0;
        if(!number(argv[10],&delivery)||!number(argv[11],&budget))ok=0;
        if(ok){kotze_work_spec w={argv[3],argv[4],argv[5],argv[6],argv[7],argv[8],argv[9],delivery,budget};
               rc=kotze_create_work(k,&w);}
    }else if(!strcmp(cmd,"status")&&argc==4){
        kotze_work_view w;rc=kotze_get_work(k,argv[3],&w);
        if(rc==KOTZE_OK)printf("work=%s state=%s mode=%s revision=%lld evidence_epoch=%lld patch=%s verification=%s trajectory=%s effect=%s actions=%d/%d candidate=%s oracle=%s resume=%s\n",
            w.id,w.state,w.mode,(long long)w.revision,(long long)w.evidence_epoch,
            w.patch_state,w.verification_state,w.trajectory_state,w.effect_state,
            w.actions_reserved,w.action_budget,w.candidate_sha,w.oracle_hash,w.resume_state);
    }else if(!strcmp(cmd,"event")&&argc==12){
        kotze_role actor;int valid_rev=0;int64_t rev=revision(argv[11],&valid_rev);
        if(!role(argv[6],&actor)||!valid_rev)ok=0;
        if(ok){kotze_event e={argv[3],argv[4],argv[5],actor,rev,
            optional(argv[7]),optional(argv[8]),optional(argv[9]),optional(argv[10])};
            rc=kotze_apply_event(k,&e);}
    }else if(!strcmp(cmd,"option-add")&&argc==7){
        int ordinal=0;if(!number(argv[5],&ordinal))ok=0;
        if(ok)rc=kotze_add_option(k,argv[3],argv[4],ordinal,argv[6]);
    }else if(!strcmp(cmd,"option-decide")&&argc==7){
        rc=kotze_decide_option(k,argv[3],argv[4],argv[5],argv[6]);
    }else if(!strcmp(cmd,"option-next")&&argc==4){
        char id[129];rc=kotze_next_option(k,argv[3],id,sizeof(id));
        if(rc==KOTZE_OK)puts(id);
    }else if(!strcmp(cmd,"action-reserve")&&argc==9){
        int approved=0;if(!number(argv[8],&approved)||approved>1)ok=0;
        if(ok)rc=kotze_admit_action(k,argv[3],argv[4],argv[5],argv[6],argv[7],approved);
    }else if(!strcmp(cmd,"action-finish")&&argc==5){
        rc=kotze_finish_action(k,argv[3],argv[4]);
    }else if(!strcmp(cmd,"success-add")&&argc==7){
        rc=kotze_record_success(k,argv[3],argv[4],argv[5],argv[6]);
    }else if(!strcmp(cmd,"success-find")&&argc==5){
        char receipt[513];rc=kotze_find_success(k,argv[3],argv[4],receipt,sizeof(receipt));
        if(rc==KOTZE_OK)puts(receipt);
    }else{kotze_close(k);return usage();}
    if(!ok){kotze_close(k);return usage();}
    if(rc<0)fprintf(stderr,"DENIED/ERROR (%d): %s\n",rc,kotze_error(k));
    else if(rc==KOTZE_REPLAY)puts("REPLAY: already committed, no new action");
    else if(rc==KOTZE_REPEAT)puts("REPEAT_BLOCKED: identical context already admitted");
    else if(strcmp(cmd,"status")&&strcmp(cmd,"option-next")&&strcmp(cmd,"success-find"))puts("OK: transaction committed");
    kotze_close(k);
    return rc<0?1:0;
}
