#pragma once
#include <openssl/hmac.h>
#include <openssl/crypto.h>
#include <arpa/inet.h>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>
#include <algorithm>
namespace onet {
constexpr size_t max_payload = 4096;
enum Type : uint8_t { DATA=1, PING, PONG, DISCOVERY, ROUTE_UPDATE, HEARTBEAT, DNS_QUERY, DNS_RESPONSE, HTTP_REQUEST, HTTP_RESPONSE, ERROR, ACK };
struct Packet { uint8_t type=DATA, ttl=16; uint64_t id=0; uint32_t src=0,dst=0; std::string payload; };
inline uint32_t ip(const std::string& s) { in_addr a{}; if(inet_pton(AF_INET,s.c_str(),&a)!=1) throw std::runtime_error("invalid IPv4 address: "+s); return ntohl(a.s_addr); }
inline std::string ipstr(uint32_t n) { in_addr a{htonl(n)}; char s[INET_ADDRSTRLEN]; inet_ntop(AF_INET,&a,s,sizeof(s)); return s; }
inline void put(std::vector<uint8_t>& b,uint64_t n,int bytes) { for(int i=bytes-1;i>=0;--i)b.push_back(uint8_t(n>>(i*8))); }
inline uint64_t get(const std::vector<uint8_t>& b,size_t off,int n) { uint64_t v=0; for(int i=0;i<n;++i)v=(v<<8)|b.at(off+i); return v; }
inline std::vector<uint8_t> encode(const Packet& p,const std::string& key) {
 if(p.payload.size()>max_payload || p.ttl==0 || p.type<DATA || p.type>ACK)throw std::runtime_error("invalid packet fields");
 std::vector<uint8_t>b={'O','N','E','T',1,p.type,p.ttl,0}; put(b,p.id,8);put(b,p.src,4);put(b,p.dst,4);put(b,p.payload.size(),2);
 b.insert(b.end(),p.payload.begin(),p.payload.end()); unsigned char mac[32]; unsigned int len=32;
 HMAC(EVP_sha256(),key.data(),int(key.size()),b.data(),b.size(),mac,&len); b.insert(b.end(),mac,mac+32); return b;
}
inline Packet decode(const std::vector<uint8_t>& b,const std::string& key) {
 if(b.size()<58 || b.size()>58+max_payload || std::string(b.begin(),b.begin()+4)!="ONET" || b[4]!=1 || b[5]<DATA || b[5]>ACK || b[6]==0 || b[7]!=0)throw std::runtime_error("invalid packet header");
 auto len=get(b,24,2); if(b.size()!=58+len)throw std::runtime_error("invalid packet length");
 unsigned char mac[32]; unsigned int ml=32; HMAC(EVP_sha256(),key.data(),int(key.size()),b.data(),b.size()-32,mac,&ml);
 if(CRYPTO_memcmp(mac,b.data()+b.size()-32,32)!=0)throw std::runtime_error("HMAC validation failed");
 return Packet{b[5],b[6],get(b,8,8),uint32_t(get(b,16,4)),uint32_t(get(b,20,4)),std::string(b.begin()+26,b.end()-32)};
}
inline std::string hex(const std::string& s) {const char* h="0123456789abcdef"; std::string r;for(unsigned char c:s){r+=h[c>>4];r+=h[c&15];}return r;}
inline std::string unhex(const std::string& s) {
 if(s=="-")return "";
 if(s.size()%2 || s.size()>max_payload*2)throw std::runtime_error("invalid hex length");
 std::string r;
 auto digit=[](char c)->int {if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;throw std::runtime_error("invalid hex");};
 for(size_t i=0;i<s.size();i+=2)r+=char(digit(s[i])*16+digit(s[i+1]));
 return r;
}
}
