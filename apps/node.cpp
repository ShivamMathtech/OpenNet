#include "packet.hpp"
#include "socket.hpp"
#include <poll.h>
#include <csignal>
#include <fstream>
#include <sstream>
#include <iostream>
#include <map>
#include <chrono>
#include <random>
#include <thread>
#include <fcntl.h>
using namespace onet;
using Clock=std::chrono::steady_clock;
static volatile std::sig_atomic_t running=1;
struct Peer {std::string host;int port=0; Clock::time_point last=Clock::now(); bool alive=true;};
static std::string quote(const std::string& s){ std::string r="\"";for(unsigned char c:s){if(c=='"'||c=='\\'){r+='\\';r+=char(c);}else if(c<32||c>=127){char b[7];snprintf(b,sizeof(b),"\\u%04x",c);r+=b;}else r+=char(c);}return r+'"'; }
class Node {
 std::string id,host,role,transport,key;int port;uint32_t address;
 FD udp,tcp;std::map<uint32_t,Peer> peers;std::map<uint32_t,uint32_t> routes;std::map<std::string,std::string> records;
 uint64_t sent=0,received=0,dropped=0,bytes_sent=0,bytes_received=0;double loss=0;int delay=0;
 std::mt19937 rng{std::random_device{}()};std::string input;
 void event(const std::string& kind,const Packet* p=nullptr,const std::string& detail="") {
  auto ms=std::chrono::duration<double,std::milli>(std::chrono::system_clock::now().time_since_epoch()).count();
  std::cout<<"{\"event\":"<<quote(kind)<<",\"node\":"<<quote(id)<<",\"time_ms\":"<<std::fixed<<ms<<",\"detail\":"<<quote(detail);
  if(p)std::cout<<",\"id\":\""<<p->id<<"\",\"type\":"<<int(p->type)<<",\"src\":"<<quote(ipstr(p->src))<<",\"dst\":"<<quote(ipstr(p->dst))<<",\"ttl\":"<<int(p->ttl)<<",\"payload_hex\":"<<quote(hex(p->payload));
  if(kind=="heartbeat")std::cout<<",\"sent\":"<<sent<<",\"received\":"<<received<<",\"dropped\":"<<dropped<<",\"bytes_sent\":"<<bytes_sent<<",\"bytes_received\":"<<bytes_received;
  std::cout<<"}"<<std::endl;
 }
 bool wire(const Packet& p,const Peer& peer,bool heartbeat=false){
  try{auto b=encode(p,key); auto a=endpoint(peer.host,peer.port);
   if(transport=="tcp"&&!heartbeat){FD fd(socket(AF_INET,SOCK_STREAM,0));if(fd.n<0)throw std::runtime_error("TCP socket failed");timeout(fd.n);
    // Nonblocking connect bounds even an unreachable LAN endpoint.
    fcntl(fd.n,F_SETFL,O_NONBLOCK);int c=connect(fd.n,(sockaddr*)&a,sizeof(a));if(c<0&&errno!=EINPROGRESS)throw std::runtime_error("TCP connect failed");
    if(c<0){pollfd f{fd.n,POLLOUT,0};int err=0;socklen_t size=sizeof(err);if(poll(&f,1,250)<=0||getsockopt(fd.n,SOL_SOCKET,SO_ERROR,&err,&size)<0||err)throw std::runtime_error("TCP connect timeout/refused");}
    fcntl(fd.n,F_SETFL,0);std::vector<uint8_t> frame;put(frame,b.size(),4);frame.insert(frame.end(),b.begin(),b.end());transfer(fd.n,frame.data(),frame.size(),true);
   }else if(sendto(udp.n,b.data(),b.size(),0,(sockaddr*)&a,sizeof(a))!=ssize_t(b.size()))throw std::runtime_error("UDP send failed");
   if(!heartbeat){++sent;bytes_sent+=b.size();}return true;
  }catch(const std::exception& e){++dropped;event("drop",&p,e.what());return false;}
 }
 void route(Packet p){
  if(p.dst==address){receive(encode(p,key));return;}
  auto r=routes.find(p.dst);if(r==routes.end()||!peers.count(r->second)){++dropped;event("drop",&p,"no route");return;}
  if(std::generate_canonical<double,32>(rng)<loss){++dropped;event("drop",&p,"injected loss");return;}
  if(delay)std::this_thread::sleep_for(std::chrono::milliseconds(delay));
  if(wire(p,peers.at(r->second)))event("forward",&p,ipstr(r->second));
 }
 void receive(const std::vector<uint8_t>& b){
  try {Packet p=decode(b,key);
   if(p.type==HEARTBEAT||p.type==DISCOVERY){if(!peers.count(p.src)||p.dst!=address)throw std::runtime_error("unconfigured neighbor");auto& peer=peers.at(p.src);peer.last=Clock::now();if(!peer.alive||p.type==DISCOVERY){peer.alive=true;event("neighbor_up",&p,ipstr(p.src));}return;}
   ++received;bytes_received+=b.size();event("receive",&p);
   if(p.dst!=address){if(role!="router"){++dropped;event("drop",&p,"endpoint cannot forward transit traffic");return;}if(p.ttl<=1){++dropped;event("drop",&p,"TTL expired");return;}--p.ttl;route(p);return;}
   event("deliver",&p);
   uint8_t type=0;std::string payload;
   if(p.type==PING){type=PONG;payload=p.payload;}
   else if(p.type==DATA){type=ACK;payload="received: "+p.payload;}
   else if(p.type==DNS_QUERY){type=DNS_RESPONSE;if(role!="dns")payload="ERROR not a DNS node";else if(records.count(p.payload))payload=records[p.payload]+" 30";else payload="NXDOMAIN";}
   else if(p.type==HTTP_REQUEST){type=HTTP_RESPONSE;if(role!="server")payload="HTTP/1.0 503 Service Unavailable\r\n\r\nNot an application server";else if(p.payload=="GET /")payload="HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\nHello from OpenNet\nBuild the Internet From First Principles\n";else payload="HTTP/1.0 404 Not Found\r\n\r\nUnknown path";}
   if(type){Packet answer{type,32,p.id,address,p.src,payload};event("reply",&answer);route(answer);}
  }catch(const std::exception& e){++dropped;event("invalid",nullptr,e.what());}
 }
 void command(const std::string& line){try{std::istringstream s(line);std::string cmd;s>>cmd;
  if(cmd=="SEND"){uint64_t seq;unsigned type,ttl;std::string dst,payload;if(!(s>>seq>>type>>dst>>ttl>>payload)||type<1||type>12||ttl<1||ttl>64)throw std::runtime_error("bad SEND command");Packet p{uint8_t(type),uint8_t(ttl),seq,address,ip(dst),unhex(payload)};event("send",&p);if(p.dst==address)receive(encode(p,key));else route(p);}
  else if(cmd=="ROUTES"){std::map<uint32_t,uint32_t> next;std::string dst,hop;while(s>>dst){if(!(s>>hop))throw std::runtime_error("route missing next hop");auto h=ip(hop);if(!peers.count(h))throw std::runtime_error("route next hop is not a neighbor");next[ip(dst)]=h;}routes=next;event("routes_updated",nullptr,std::to_string(routes.size()));}
  else if(cmd=="FAULT"){double l;int d;if(!(s>>l>>d)||l<0||l>1||d<0||d>500)throw std::runtime_error("fault bounds: loss 0..1, delay 0..500ms");loss=l;delay=d;event("fault_updated");}
  else if(cmd=="STOP")running=0;else throw std::runtime_error("unknown command");
 }catch(const std::exception& e){event("command_error",nullptr,e.what());}}
public:
 explicit Node(const std::string& path){std::ifstream f(path);if(!(f>>id>>address_text>>host>>port>>role>>transport))throw std::runtime_error("bad node configuration");address=ip(address_text);const char* k=getenv("OPENNET_KEY");if(!k||std::string(k).size()<32)throw std::runtime_error("OPENNET_KEY must have at least 32 characters");key=k;
  std::string kind,a,h;int p;while(f>>kind){if(kind=="peer"){if(!(f>>a>>h>>p))throw std::runtime_error("bad peer");endpoint(h,p);peers.emplace(ip(a),Peer{h,p});}else if(kind=="record"){if(!(f>>a>>h))throw std::runtime_error("bad record");records[a]=h;}else throw std::runtime_error("unknown configuration entry");}
  udp.n=bind_socket(host,port,SOCK_DGRAM);tcp.n=bind_socket(host,port,SOCK_STREAM);
 }
 std::string address_text;
 void run(){event("started");for(const auto& [a,p]:peers)wire(Packet{DISCOVERY,1,0,address,a,id+" "+role+" "+std::to_string(port)},p,true);
  auto last=Clock::now()-std::chrono::seconds(2);
  while(running){pollfd fds[]={{udp.n,POLLIN,0},{tcp.n,POLLIN,0},{STDIN_FILENO,POLLIN,0}};int n=poll(fds,3,100);if(n<0&&errno!=EINTR)throw std::runtime_error("poll failed");
   if(fds[0].revents&POLLIN){std::vector<uint8_t>b(65536);auto k=recv(udp.n,b.data(),b.size(),0);if(k>0){b.resize(size_t(k));receive(b);}}
   if(fds[1].revents&POLLIN){FD fd(accept(tcp.n,nullptr,nullptr));if(fd.n>=0){timeout(fd.n);try{receive(read_frame(fd.n));}catch(const std::exception& e){++dropped;event("invalid",nullptr,e.what());}}}
   if(fds[2].revents&POLLIN){char buf[8192];auto k=read(STDIN_FILENO,buf,sizeof(buf));if(k<=0)break;input.append(buf,size_t(k));size_t pos;while((pos=input.find('\n'))!=std::string::npos){command(input.substr(0,pos));input.erase(0,pos+1);}if(input.size()>65536)throw std::runtime_error("control input too large");}
   if(fds[2].revents&POLLHUP)break;
   if(Clock::now()-last>=std::chrono::seconds(1)){last=Clock::now();event("heartbeat");for(auto& [a,p]:peers){wire(Packet{HEARTBEAT,1,0,address,a,id},p,true);if(last-p.last>std::chrono::seconds(3)&&p.alive){p.alive=false;event("neighbor_down",nullptr,ipstr(a));}}}
  }event("stopped");
 }
};
int main(int argc,char** argv){std::signal(SIGTERM,[](int){running=0;});std::signal(SIGINT,[](int){running=0;});std::signal(SIGPIPE,SIG_IGN);try{if(argc!=2)throw std::runtime_error("usage: opennet-node CONFIG");Node node(argv[1]);node.run();return 0;}catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}}
