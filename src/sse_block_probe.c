#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct {uint32_t s,e;uint8_t f;} Obs;
static inline uint32_t mx_from_mask(uint8_t f){uint32_t m=0x1f80u;if(f&1)m|=1;if(f&2)m|=4;if(f&4)m|=8;if(f&8)m|=16;if(f&16)m|=32;return m;}
static inline uint8_t mapf(uint32_t m){uint8_t f=0;if(m&1)f|=1;if(m&4)f|=2;if(m&8)f|=4;if(m&16)f|=8;if(m&32)f|=16;return f;}
static Obs candidate(uint32_t a,uint32_t b,uint8_t initial){uint32_t save,mx=mx_from_mask(initial),s,e,after;__asm__ volatile("stmxcsr %0":"=m"(save));__asm__ volatile("ldmxcsr %0"::"m"(mx):"memory");__asm__ volatile(
 "movd %2, %%xmm0\n\t"
 "movd %3, %%xmm1\n\t"
 "pxor %%xmm2, %%xmm2\n\t"
 "pxor %%xmm3, %%xmm3\n\t"
 "orps %%xmm1, %%xmm2\n\t"
 "orps %%xmm0, %%xmm3\n\t"
 "addss %%xmm1, %%xmm0\n\t"
 "subss %%xmm0, %%xmm2\n\t"
 "addss %%xmm2, %%xmm3\n\t"
 "addss %%xmm0, %%xmm2\n\t"
 "subss %%xmm2, %%xmm1\n\t"
 "addss %%xmm1, %%xmm3\n\t"
 "movd %%xmm0, %0\n\t"
 "movd %%xmm3, %1\n\t"
 :"=r"(s),"=r"(e):"r"(a),"r"(b):"xmm0","xmm1","xmm2","xmm3","memory");__asm__ volatile("stmxcsr %0":"=m"(after)::"memory");__asm__ volatile("ldmxcsr %0"::"m"(save):"memory");Obs o={s,e,mapf(after)};return o;}
static Obs reference(uint32_t a,uint32_t b,uint8_t initial){uint32_t save,mx=mx_from_mask(initial),s,e,after;__asm__ volatile("stmxcsr %0":"=m"(save));__asm__ volatile("ldmxcsr %0"::"m"(mx):"memory");__asm__ volatile(
 "movd %2, %%xmm0\n\t" /* a */
 "movd %3, %%xmm1\n\t" /* b */
 "movaps %%xmm0, %%xmm2\n\t" /* a */
 "movaps %%xmm1, %%xmm3\n\t" /* b */
 "movaps %%xmm0, %%xmm4\n\t"
 "addss %%xmm1, %%xmm4\n\t" /* s */
 "movaps %%xmm4, %%xmm5\n\t"
 "subss %%xmm1, %%xmm5\n\t" /* x=s-b */
 "movaps %%xmm4, %%xmm6\n\t"
 "subss %%xmm5, %%xmm6\n\t" /* y=s-x */
 "movaps %%xmm2, %%xmm7\n\t"
 "subss %%xmm5, %%xmm7\n\t" /* dx=a-x */
 "movaps %%xmm3, %%xmm8\n\t"
 "subss %%xmm6, %%xmm8\n\t" /* dy=b-y */
 "addss %%xmm8, %%xmm7\n\t" /* e */
 "movd %%xmm4, %0\n\t"
 "movd %%xmm7, %1\n\t"
 :"=r"(s),"=r"(e):"r"(a),"r"(b):"xmm0","xmm1","xmm2","xmm3","xmm4","xmm5","xmm6","xmm7","xmm8","memory");__asm__ volatile("stmxcsr %0":"=m"(after)::"memory");__asm__ volatile("ldmxcsr %0"::"m"(save):"memory");Obs o={s,e,mapf(after)};return o;}
int main(int argc,char**argv){if(argc!=3){fprintf(stderr,"usage pool.bin out.csv\n");return 2;}FILE*in=fopen(argv[1],"rb"),*out=fopen(argv[2],"w");if(!in||!out)return 2;fprintf(out,"case,initial,a,b,ref_s,ref_e,ref_f,cand_s,cand_e,cand_f\n");uint32_t a,b;unsigned i=0;unsigned bad=0;while(fread(&a,4,1,in)==1&&fread(&b,4,1,in)==1){for(int m=0;m<32;m++){Obs r=reference(a,b,m),c=candidate(a,b,m);if(r.s!=c.s||r.e!=c.e||r.f!=c.f)bad++;fprintf(out,"%u,%d,0x%08x,0x%08x,0x%08x,0x%08x,%u,0x%08x,0x%08x,%u\n",i,m,a,b,r.s,r.e,r.f,c.s,c.e,c.f);}i++;}fclose(in);fclose(out);fprintf(stderr,"cases=%u observations=%u mismatches=%u\n",i,i*32,bad);return bad?1:0;}
