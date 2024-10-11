/* -*-mode:c++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */

#include <vector>
#include <string>

#include "copa_attack_queue.hh"
#include "util.hh"
#include "ezio.hh"
#include "packetshell.cc"

using namespace std;

int main(int argc, char *argv[])
{
    try
    {
        const bool passthrough_until_signal = getenv("MAHIMAHI_PASSTHROUGH_UNTIL_SIGNAL");

        /* clear environment while running as root */
        char **const user_environment = environ;
        environ = nullptr;

        check_requirements(argc, argv);

        int arg_num = 2;

        if (argc < arg_num)
        {
            throw runtime_error("Usage: " + string(argv[0]) + " delay_budget-milliseconds [command...]");
        }

        const uint64_t delay_budget = myatoi(argv[1]);

        vector<string> command;

        if (argc == arg_num)
        {
            command.push_back(shell_path());
        }
        else
        {
            for (int i = arg_num; i < argc; i++)
            {
                command.push_back(argv[i]);
            }
        }

        PacketShell<CopaAttackQueue> delay_shell_app("copa_attack", user_environment, passthrough_until_signal);

        delay_shell_app.start_uplink("[copa_attack] ",
                                     command,
                                     delay_budget);
        delay_shell_app.start_downlink(delay_budget);
        return delay_shell_app.wait_for_exit();
    }
    catch (const exception &e)
    {
        print_exception(e);
        return EXIT_FAILURE;
    }
}
