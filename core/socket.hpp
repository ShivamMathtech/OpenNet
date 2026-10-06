#pragma once
#include <sys/socket.h>
#include <unistd.h>
#include <cerrno>
#include <cstring>
#include <stdexcept>
#include <vector>
#include "packet.hpp"
namespace onet {
struct FD { int n=-1; explicit FD(int value=-1):n(value){} ~FD(){if(n>=0)::close(n);} FD(const FD&)=delete; FD& operator=(const FD&)=delete; };
inline sockaddr_in endpoint(const std::string& host,int port) { sockaddr_in a{};a.sin_family=AF_INET;a.sin_port=htons(uint16_t(port));if(port<1||port>65535||inet_pton(AF_INET,host.c_str(),&a.sin_addr)!=1)throw std::runtime_error("endpoint needs IPv4 and valid port");return a; }
inline void timeout(int fd) { timeval t{0,250000};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&t,sizeof(t));setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&t,sizeof(t)); }
inline int bind_socket(const std::string& host,int port,int type) { FD fd(socket(AF_INET,type,0));if(fd.n<0)throw std::runtime_error("socket creation failed");if(type==SOCK_STREAM){int one=1;setsockopt(fd.n,SOL_SOCKET,SO_REUSEADDR,&one,sizeof(one));}auto a=endpoint(host,port);if(bind(fd.n,(sockaddr*)&a,sizeof(a))<0)throw std::runtime_error("bind "+host+":"+std::to_string(port)+": "+strerror(errno));if(type==SOCK_STREAM&&listen(fd.n,64)<0)throw std::runtime_error("listen failed");int n=fd.n;fd.n=-1;return n; }
inline void transfer(int fd,uint8_t* data,size_t n,bool writing) {while(n){auto k=writing?send(fd,data,n,MSG_NOSIGNAL):recv(fd,data,n,0);if(k<=0)throw std::runtime_error(writing?"TCP send failed":"TCP frame incomplete/timeout");n-=size_t(k);data+=k;} }
inline std::vector<uint8_t> read_frame(int fd) {uint8_t h[4];transfer(fd,h,4,false);size_t n=(size_t(h[0])<<24)|(size_t(h[1])<<16)|(size_t(h[2])<<8)|h[3];if(n<58||n>4154)throw std::runtime_error("TCP frame length invalid");std::vector<uint8_t>b(n);transfer(fd,b.data(),n,false);return b;}
}
