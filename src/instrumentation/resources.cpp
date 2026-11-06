#include "dynagraph/instrumentation/resources.hpp"
#include <cerrno>
#include <charconv>
#include <limits>
#include <sstream>
#include <stdexcept>
#ifdef __linux__
#include <fcntl.h>
#include <sched.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <time.h>
#include <unistd.h>
#endif

namespace dynagraph {
namespace {
void require(bool value) { if (!value) { throw std::runtime_error("resource observation unavailable or exceeds bound"); } }
#ifdef __linux__
std::string quote(const std::string& value) {
    std::string out="\"";
    constexpr char hex[]="0123456789abcdef";
    for (const unsigned char c : value) {
        if (c=='"' || c=='\\') { out+='\\'; out+=static_cast<char>(c); }
        else if (c<32) { out+="\\u00"; out+=hex[c>>4]; out+=hex[c&15]; }
        else { out+=static_cast<char>(c); }
    }
    return out+'"';
}
struct Fact { std::string value; int error=0; };
#ifdef __linux__
struct Descriptor {
    int value;
    explicit Descriptor(int fd):value(fd) {}
    ~Descriptor() { if (value>=0) { (void)close(value); } }
    Descriptor(const Descriptor&)=delete;
    Descriptor& operator=(const Descriptor&)=delete;
};
Fact read_at(int directory, const std::string& name, std::size_t cap=16384) {
    Descriptor fd(openat(directory,name.c_str(),O_RDONLY|O_NONBLOCK|O_CLOEXEC|O_NOFOLLOW));
    if (fd.value<0) { return {{},errno}; }
    struct stat info{};
    if (fstat(fd.value,&info)!=0) { return {{},errno}; }
    if (!S_ISREG(info.st_mode)) { return {{},EINVAL}; }
    Fact result; char buffer[4096];
    for (;;) {
        const auto count=read(fd.value,buffer,sizeof(buffer));
        if (count<0) { return {{},errno}; }
        if (count==0) { return result; }
        const auto amount=static_cast<std::size_t>(count);
        if (result.value.size()+amount>cap) { return {{},EOVERFLOW}; }
        result.value.append(buffer,amount);
    }
}
std::vector<int> affinity(int pid) {
    std::vector<int> result;
    // RAII without a variable-sized kernel allocation; fixed 8192-CPU mask.
    alignas(cpu_set_t) unsigned long storage[1024/sizeof(unsigned long)]{};
    auto* mask=reinterpret_cast<cpu_set_t*>(storage);
    require(sched_getaffinity(pid,sizeof(storage),mask)==0);
    for (int cpu=0;cpu<8192;++cpu) {
        if (CPU_ISSET_S(static_cast<std::size_t>(cpu),sizeof(storage),mask)) { result.push_back(cpu); }
    }
    require(!result.empty() && result.size()<=64); return result;
}
#else
Fact read_at(int, const std::string&, std::size_t=16384) { return {{},ENOTSUP}; }
#endif
void emit(std::ostream& out, const Fact& fact) {
    out << "{\"value\":";
    if (fact.error) { out << "null"; } else { out << quote(fact.value); }
    out << ",\"errno\":" << fact.error << '}';
}
void array(std::ostream& out,const std::vector<int>& cpus) {
    out << '['; bool first=true;
    for (int cpu:cpus) { if (!first) { out << ','; } first=false; out << cpu; }
    out << ']';
}
std::uint64_t number(const std::string& raw) {
    std::uint64_t value=0;
    const auto parsed=std::from_chars(raw.data(),raw.data()+raw.size(),value);
    require(!raw.empty() && (raw.size()==1 || raw.front()!='0') && parsed.ec==std::errc{} &&
        parsed.ptr==raw.data()+raw.size() && value>0 && value<=static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()));
    return value;
}
#endif
}
std::uint64_t resource_monotonic_ns() {
#ifdef __linux__
    struct timespec value{};
    require(clock_gettime(CLOCK_MONOTONIC,&value)==0 && value.tv_sec>=0 && value.tv_nsec>=0 && value.tv_nsec<1000000000);
    const auto seconds=static_cast<std::uint64_t>(value.tv_sec);
    require(seconds<=static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())/1000000000ULL);
    return seconds*1000000000ULL+static_cast<std::uint64_t>(value.tv_nsec);
#else
    throw std::runtime_error("Linux CLOCK_MONOTONIC resource observations required");
#endif
}
void ResourceObservations::load_paths(const std::string& path) {
#ifndef __linux__
    (void)path; require(false);
#else
    require(paths_.empty() && samples_.empty());
    const auto raw=read_at(AT_FDCWD,path,65536); require(raw.error==0);
    std::istringstream in(raw.value); std::string line;
    require(static_cast<bool>(std::getline(in,line)) && line=="DYNAGRAPH_RESOURCE_PATHS 1");
    require(static_cast<bool>(std::getline(in,line))); armed_ns_=number(line);
    require(static_cast<bool>(std::getline(in,boot_id_)) && boot_id_.size()==36);
    require(static_cast<bool>(std::getline(in,line))); const auto count=number(line);
    require(count<=max_paths);
    for (std::uint64_t i=0;i<count;++i) {
        require(static_cast<bool>(std::getline(in,line)) && !line.empty() && line.front()=='/' && line.size()<=4096 && line.find('\0')==std::string::npos);
        paths_.push_back(line);
    }
    require(!std::getline(in,line) && !raw.value.empty() && raw.value.back()=='\n');
#endif
}
void ResourceObservations::before() { require(samples_.empty() && !paths_.empty()); capture("pre",false); }
void ResourceObservations::workload(bool exit) {
    require(samples_.size()==(exit ? 2U : 1U)); capture(exit ? "workload_exit" : "workload_entry",true);
}
void ResourceObservations::after() {
    require(samples_.size()==3 || samples_.size()==1); capture("post",false);
}
void ResourceObservations::capture(const char* boundary,bool in_region) {
#ifdef __linux__
    require(samples_.size()<4);
    const auto start=resource_monotonic_ns();
    const int pid=static_cast<int>(getpid()),tid=static_cast<int>(syscall(SYS_gettid));
    const auto process="/proc/self/task/"+std::to_string(pid);
    const auto task="/proc/self/task/"+std::to_string(tid);
    const auto stat_before=read_at(AT_FDCWD,process+"/stat");
    const auto member=read_at(AT_FDCWD,"/proc/self/cgroup");
    const auto mounts=read_at(AT_FDCWD,"/proc/self/mountinfo",65536);
    const auto online=read_at(AT_FDCWD,"/sys/devices/system/cpu/online");
    std::ostringstream out;
    out << "{\"boundary\":" << quote(boundary) << ",\"region_id\":" << (in_region ? "0" : "null")
        << ",\"start_ns\":" << start << ",\"pid\":" << pid << ",\"tid\":" << tid << ",\"process_affinity\":";
    const auto cpus=affinity(pid); array(out,cpus);
    out << ",\"thread_affinity\":"; array(out,affinity(0));
    out << ",\"cpu\":" << sched_getcpu() << ",\"process_stat\":"; emit(out,stat_before);
    out << ",\"task_stat\":"; emit(out,read_at(AT_FDCWD,task+"/stat"));
    out << ",\"task_status\":"; emit(out,read_at(AT_FDCWD,task+"/status"));
    out << ",\"membership\":"; emit(out,member);
    out << ",\"mountinfo\":"; emit(out,mounts);
    out << ",\"online\":"; emit(out,online);
    out << ",\"boot_id\":"; emit(out,read_at(AT_FDCWD,"/proc/sys/kernel/random/boot_id"));
    out << ",\"process_schedstat\":"; emit(out,read_at(AT_FDCWD,process+"/schedstat"));
    out << ",\"thread_schedstat\":"; emit(out,read_at(AT_FDCWD,task+"/schedstat"));
    out << ",\"groups\":["; bool first=true;
    for (const auto& path:paths_) {
        if (!first) { out << ','; } first=false;
        Descriptor directory(open(path.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW));
        const int error=directory.value<0 ? errno : 0;
        out << "{\"path\":" << quote(path) << ",\"open_errno\":" << error << ",\"identity\":";
        if (error) { out << "null"; }
        else {
            struct stat info{}; require(fstat(directory.value,&info)==0);
            out << "{\"device_major\":" << major(info.st_dev) << ",\"device_minor\":" << minor(info.st_dev) << ",\"inode\":" << info.st_ino << '}';
        }
        for (const auto* name:{"cpu.max","cpuset.cpus.effective","cpu.stat","cpu.pressure"}) {
            out << ',' << quote(name) << ':';
            emit(out,error ? Fact{{},error} : read_at(directory.value,name));
        }
        out << '}';
    }
    out << "],\"topology\":["; first=true;
    for (int cpu:cpus) {
        if (!first) { out << ','; } first=false;
        const auto path="/sys/devices/system/cpu/cpu"+std::to_string(cpu)+"/topology/";
        out << "{\"cpu\":" << cpu;
        for (const auto* name:{"physical_package_id","core_id","thread_siblings_list"}) {
            out << ',' << quote(name) << ':'; emit(out,read_at(AT_FDCWD,path+name));
        }
        out << '}';
    }
    out << "],\"process_stat_after\":"; emit(out,read_at(AT_FDCWD,process+"/stat"));
    out << ",\"membership_after\":"; emit(out,read_at(AT_FDCWD,"/proc/self/cgroup"));
    out << ",\"mountinfo_after\":"; emit(out,read_at(AT_FDCWD,"/proc/self/mountinfo",65536));
    out << ",\"online_after\":"; emit(out,read_at(AT_FDCWD,"/sys/devices/system/cpu/online"));
    out << ",\"end_ns\":" << resource_monotonic_ns() << '}';
    const auto text=out.str(); require(bytes_+text.size()<=max_bytes-4096);
    samples_.push_back(text); bytes_+=text.size();
#else
    (void)boundary; (void)in_region; require(false);
#endif
}
void ResourceObservations::publish(const std::string& path) const {
#ifdef __linux__
    require(samples_.size()==4 || samples_.size()==2);
    std::ostringstream out;
    out << "{\"schema\":\"dynagraph-resource-native\",\"schema_version\":1,\"clock\":\"CLOCK_MONOTONIC\",\"measurement_eligible\":false,\"configuration\":{\"armed_ns\":" << armed_ns_
        << ",\"boot_id\":" << quote(boot_id_) << ",\"paths\":[";
    for (std::size_t i=0;i<paths_.size();++i) { if (i) { out << ','; } out << quote(paths_[i]); }
    out << "]},\"samples\":[";
    for (std::size_t i=0;i<samples_.size();++i) { if (i) { out << ','; } out << samples_[i]; }
    out << "]}\n";
    const auto text=out.str(); require(text.size()<=max_bytes);
    Descriptor fd(open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600)); require(fd.value>=0);
    const auto count=write(fd.value,text.data(),text.size()); const bool synced=fsync(fd.value)==0;
    const bool closed=close(fd.value)==0; fd.value=-1;
    if (count!=static_cast<ssize_t>(text.size()) || !synced || !closed) { (void)unlink(path.c_str()); require(false); }
#else
    (void)path; require(false);
#endif
}
} // namespace dynagraph
