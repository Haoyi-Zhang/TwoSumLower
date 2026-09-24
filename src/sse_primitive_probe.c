#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint32_t w; uint8_t f; uint32_t raw_mxcsr; } R;
static inline uint8_t mapf(uint32_t m){uint8_t f=0;if(m&1)f|=1;if(m&4)f|=2;if(m&8)f|=4;if(m&16)f|=8;if(m&32)f|=16;return f;}
static R runop(int op,uint32_t a,uint32_t b,uint32_t mask){
 uint32_t save,base=0x1f80u,out=0,after;
 __asm__ volatile("stmxcsr %0":"=m"(save));
 __asm__ volatile("ldmxcsr %0"::"m"(base):"memory");
 switch(op){
 #define BIN(OP) __asm__ volatile("movd %1, %%xmm0\n\tmovd %2, %%xmm1\n\t" OP " %%xmm1, %%xmm0\n\tmovd %%xmm0, %0":"=r"(out):"r"(a),"r"(b):"xmm0","xmm1","memory")
 case 0: BIN("addss"); break;
 case 1: BIN("subss"); break;
 case 2: BIN("mulss"); break;
 case 3: BIN("minss"); break;
 case 4: BIN("maxss"); break;
 case 5: BIN("andps"); break;
 case 6: BIN("orps"); break;
 case 7: BIN("xorps"); break;
 #undef BIN
 case 8:
   __asm__ volatile("movd %1, %%xmm1\n\tmovd %2, %%xmm2\n\tmovd %3, %%xmm0\n\tblendvps %%xmm2, %%xmm1\n\tmovd %%xmm1, %0":"=r"(out):"r"(a),"r"(b),"r"(mask):"xmm0","xmm1","xmm2","memory");break;
 #define CMP(N) __asm__ volatile("movd %1, %%xmm0\n\tmovd %2, %%xmm1\n\tcmpss $" #N ", %%xmm1, %%xmm0\n\tmovd %%xmm0, %0":"=r"(out):"r"(a),"r"(b):"xmm0","xmm1","memory")
 case 9: CMP(0);break; case 10:CMP(1);break; case 11:CMP(2);break; case 12:CMP(3);break;
 case 13:CMP(4);break; case 14:CMP(5);break; case 15:CMP(6);break; case 16:CMP(7);break;
 #undef CMP
 default: abort();
 }
 __asm__ volatile("stmxcsr %0":"=m"(after)::"memory");
 __asm__ volatile("ldmxcsr %0"::"m"(save):"memory");
 R r={out,mapf(after),after};return r;
}
int main(int argc,char**argv){if(argc!=3){fprintf(stderr,"usage: %s pool.bin out.csv\n",argv[0]);return 2;}FILE*in=fopen(argv[1],"rb");FILE*out=fopen(argv[2],"w");if(!in||!out){perror("file");return 2;}uint32_t a,b;unsigned i=0;fprintf(out,"case,op,a,b,mask,out,flags,mxcsr\n");while(fread(&a,4,1,in)==1&&fread(&b,4,1,in)==1){for(int op=0;op<17;op++){uint32_t masks[2]={0,0x80000000u};int nm=op==8?2:1;for(int j=0;j<nm;j++){R r=runop(op,a,b,masks[j]);fprintf(out,"%u,%d,0x%08x,0x%08x,0x%08x,0x%08x,%u,0x%08x\n",i,op,a,b,masks[j],r.w,r.f,r.raw_mxcsr);}}i++;}fclose(in);fclose(out);fprintf(stderr,"cases=%u records=%u\n",i,i*18);return 0;}
