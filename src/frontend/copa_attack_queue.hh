/* -*-mode:c++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */

#ifndef COPA_ATTACK_QUEUE_HH
#define COPA_ATTACK_QUEUE_HH

#include <queue>
#include <cstdint>
#include <string>

#include "file_descriptor.hh"

class CopaAttackQueue
{
private:
    uint64_t delay_budget_;
    std::queue<std::pair<uint64_t, std::string>> packet_queue_;
    /* release timestamp, contents */

public:
    CopaAttackQueue(const uint64_t &delay_budget);

    void read_packet(const std::string &contents);

    void write_packets(FileDescriptor &fd);

    unsigned int wait_time(void) const;

    bool pending_output(void) const { return wait_time() <= 0; }

    static bool finished(void) { return false; }
};

#endif /* COPA_ATTACK_QUEUE_HH */
