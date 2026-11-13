#include "kotze_protocol.h"
#include <string.h>
static int valid_id(const char *s){
    if(!s||!*s)return 0;
    size_t n=strlen(s);if(n>128)return 0;
    for(size_t i=0;i<n;i++){
        unsigned char c=(unsigned char)s[i];
        if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||
             (c>='0'&&c<='9')||c=='_'||c=='-'||
             c=='.'||c==':'||c=='/'))return 0;
    }
    return 1;
}
int kp_parse(const char *data,size_t len,const char *allowed,kp_request *out){
    if(!data||!allowed||!out||!valid_id(allowed)||
       len<2||len>512||data[len-1]!='\n')return KP_BAD;
    if(memchr(data,'\0',len)||memchr(data,'\r',len)||
       memchr(data,'\t',len)||memchr(data,'\n',len-1))return KP_BAD;
    char line[513];memcpy(line,data,len-1);line[len-1]='\0';
    for(size_t i=0;i<len-1;i++)
        if((unsigned char)line[i]<32||(unsigned char)line[i]>126)return KP_BAD;
    char *tokens[8]={0},*save=NULL;unsigned count=0;
    for(char *t=strtok_r(line," ",&save);t;t=strtok_r(NULL," ",&save)){
        if(count>=8)return KP_BAD;
        tokens[count++]=t;
    }
    if(count<4||strcmp(tokens[0],"V1")||
       !valid_id(tokens[2])||!valid_id(tokens[3]))return KP_BAD;
    if(strcmp(tokens[2],allowed))return KP_DENIED;
    kp_request v;memset(&v,0,sizeof(v));
    memcpy(v.work_id,tokens[2],strlen(tokens[2])+1);
    memcpy(v.object_key,tokens[3],strlen(tokens[3])+1);
    if(!strcmp(tokens[1],"GET")){
        if(count!=4)return KP_BAD;
        v.operation=KP_ENTRY;
    }else if(!strcmp(tokens[1],"EDGES")){
        if(count!=7)return KP_BAD;
        v.operation=KP_EDGES;
        if(!strcmp(tokens[4],"OUT"))v.direction=1;
        else if(!strcmp(tokens[4],"IN"))v.direction=2;
        else return KP_BAD;
        if(strcmp(tokens[5],"-")){
            if(!valid_id(tokens[5]))return KP_BAD;
            memcpy(v.after_key,tokens[5],strlen(tokens[5])+1);
        }
        unsigned limit=0;
        if(!tokens[6][0])return KP_BAD;
        for(const char *p=tokens[6];*p;p++){
            if(*p<'0'||*p>'9')return KP_BAD;
            limit=limit*10u+(unsigned)(*p-'0');
            if(limit>64)return KP_BAD;
        }
        if(!limit)return KP_BAD;
        v.limit=limit;
    }else return KP_BAD;
    *out=v;return KP_OK;
}
