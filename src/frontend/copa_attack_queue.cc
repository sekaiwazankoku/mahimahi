/* -*-mode:c++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */

#include <limits>

#include "copa_attack_queue.hh"
#include "timestamp.hh"

using namespace std;

CopaAttackQueue::CopaAttackQueue(const uint64_t &delay_budget) : delay_budget_(delay_budget),
                                                                 packet_queue_()
{
    srand(time(NULL));
}

void CopaAttackQueue::read_packet(const string &contents)
{
    uint64_t dequeue_time = timestamp();
    uint64_t delay = 0;
    if (delay_budget_ > 0 && packet_queue_.empty())
    {
        // delay = rand() % delay_budget_;
        delay = delay_budget_;
    }
    dequeue_time += delay;
    packet_queue_.emplace(dequeue_time, contents);
}

void CopaAttackQueue::write_packets(FileDescriptor &fd)
{
    while ((!packet_queue_.empty()) && (packet_queue_.front().first <= timestamp()))
    {
        fd.write(packet_queue_.front().second);
        packet_queue_.pop();
    }
}

unsigned int CopaAttackQueue::wait_time(void) const
{
    if (packet_queue_.empty())
    {
        return numeric_limits<uint16_t>::max();
    }

    const auto now = timestamp();

    if (packet_queue_.front().first <= now)
    {
        return 0;
    }
    else
    {
        return packet_queue_.front().first - now;
    }
}
