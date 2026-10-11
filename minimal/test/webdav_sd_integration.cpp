#include "WebDavSession.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <string>
#include <algorithm>
#include <cstdio>
using namespace RiscWebDav;
extern "C" const risc_storage_volume_api_v1* webdav_real_volume();
extern "C" void webdav_real_export(int);
extern "C" void webdav_real_absent(int);
extern "C" void webdav_real_worker(int);
static const risc_storage_volume_api_v1*volume;
static std::string wire,output;static size_t offset;static bool closed;
static unsigned request(const char*method,const char*path,const std::string&body="",const char*headers=""){
 wire=std::string(method)+" "+path+" HTTP/1.1\r\nHost: local\r\n"+headers+"Content-Length: "+std::to_string(body.size())+"\r\n\r\n"+body;offset=0;output.clear();closed=false;
 Hooks h{nullptr,[](void*){return true;},[](void*,const Request&,AuthPhase,const void*,size_t){return true;},"Digest realm=\"fixture\"",std::malloc,std::free};
 Connection c{nullptr,1,[](void*,uint64_t,void*b,uint32_t n,uint32_t*out)->int32_t{*out=std::min<size_t>(n,wire.size()-offset);if(!*out)return 2;memcpy(b,wire.data()+offset,*out);offset+=*out;return 0;},[](void*,uint64_t,const void*b,uint32_t n,uint32_t*out)->int32_t{*out=std::min<uint32_t>(n,251);output.append(static_cast<const char*>(b),*out);return 0;},[](void*,uint64_t)->int32_t{closed=true;return 0;}};
 Session s;if(!s.begin(volume,h,c,0,100000)){assert(s.state()==SessionState::Retained);return 999;}for(unsigned i=0;i<100000&&s.state()!=SessionState::Done&&s.state()!=SessionState::Retained;i++)s.tick(i);assert(s.state()==SessionState::Done&&closed);return s.status();
}
int main(){
 volume=webdav_real_volume();
 assert(request("MKCOL","/dav")==201);
 assert(request("PUT","/dav/test.txt","first")==201);
 assert(request("PUT","/dav/test.txt","replacement")==204);
 assert(request("GET","/dav/test.txt")==200);assert(output.substr(output.find("\r\n\r\n")+4)=="replacement");
 assert(request("PUT","/dav/large.bin",std::string(128*1024,'L'))==201);
 assert(request("GET","/dav/large.bin")==200);assert(output.substr(output.find("\r\n\r\n")+4)==std::string(128*1024,'L'));
 assert(request("COPY","/dav","","Destination: /dav-copy\r\nOverwrite: F\r\n")==201);
 assert(request("GET","/dav-copy/test.txt")==200);assert(output.substr(output.find("\r\n\r\n")+4)=="replacement");
 assert(request("MOVE","/dav-copy/test.txt","","Destination: /dav-copy/moved.txt\r\nOverwrite: F\r\n")==201);
 assert(request("PROPFIND","/dav-copy","","Depth: 1\r\n")==207);assert(output.find("moved.txt")!=std::string::npos);
 webdav_real_export(1);assert(request("GET","/dav/test.txt")==503);webdav_real_export(0);
 assert(request("GET","/dav/test.txt")==200);
 webdav_real_worker(1);assert(request("GET","/dav/test.txt")==503);webdav_real_worker(0);assert(request("GET","/dav/test.txt")==200);
 assert(request("DELETE","/dav-copy")==204);assert(request("GET","/dav-copy/moved.txt")==404);
 assert(request("DELETE","/dav")==204);
 // A failed native sector transport retains the production SD lease; no remount or cleanup follows.
 webdav_real_absent(1);assert(request("GET","/dav/test.txt")==999);assert(!closed);
 puts("Production X4 async-v3 SD + FatFs + shared WebDAV: streamed PUT/GET, atomic overwrite, recursive COPY/DELETE, MOVE, PROPFIND USB export/recovery, async-install exclusion and removed-media retention PASS");
}
