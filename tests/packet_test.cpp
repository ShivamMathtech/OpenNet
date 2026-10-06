#include "packet.hpp"
#include <iostream>
using namespace onet;
void check(bool b){if(!b)throw std::runtime_error("test assertion failed");}
template<class F>void rejects(F f){bool failed=false;try{f();}catch(const std::exception&){failed=true;}check(failed);}
int main(){const std::string k(64,'a');Packet p{PING,16,123,ip("10.0.0.1"),ip("10.0.0.2"),std::string("a\0b",3)};auto b=encode(p,k);auto q=decode(b,k);check(q.id==p.id&&q.payload==p.payload&&q.src==p.src&&q.dst==p.dst&&q.ttl==16);check(ipstr(p.src)=="10.0.0.1");rejects([&]{decode(b,"wrong");});b[26]^=1;rejects([&]{decode(b,k);});rejects([&]{decode({},k);});rejects([&]{ip("300.1.1.1");});p.ttl=0;rejects([&]{encode(p,k);});p.ttl=1;p.payload=std::string(4097,'x');rejects([&]{encode(p,k);});check(unhex(hex("hello"))=="hello");rejects([&]{unhex("xy");});std::cout<<"Packet roundtrip, HMAC, corruption, bounds, TTL, IPv4 and hex tests passed\n";}
