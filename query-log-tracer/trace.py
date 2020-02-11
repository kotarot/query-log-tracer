#!/usr/bin/env python3

import argparse
import glob
import gzip
import re
import sqlparse


parser = argparse.ArgumentParser(description='query-log-tracer')

# Log location
parser.add_argument('--log-file', help='Input log file')
parser.add_argument('--log-dir', help='Directory that contains input log files')

# Search (or trace) target options
parser.add_argument('--target-table', help='Table name of your trace target')
parser.add_argument('--target-column', help='Column name of you trace target')
parser.add_argument('--filter-column', help='Column name that should be used for search filtering')
parser.add_argument('--filter-value', help='Value that should be used for search filtering')

args = parser.parse_args()


# History of the values
histories = []


def search(f, target_table, target_column, filter_column, filter_value):

    target_query_commands = ['INSERT', 'UPDATE']

    # Regular expression for Time
    last_date = ''
    time_pattern = r'^\d{1,2}:\d{1,2}:\d{1,2}$'
    time_repattern = re.compile(time_pattern)
    iso8601_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}\:\d{2}\:\d{2}\.\d+Z$'
    iso8601_repattern = re.compile(iso8601_pattern)

    line = f.readline()
    while line:
        if type(line) is not str:
            try:
                line = line.decode('utf-8')
            except UnicodeDecodeError:
                # if the line contains non-UTF-8 byte string, skip it
                line = f.readline()
                continue

        line = line.rstrip('\r\n')
        terms = line.split() # split by whitespaces

        # Note: Usual MySQL log format:
        # <Time> <Id> <Command> <Argument>
        log_time = log_id = log_command = log_argument = ''
        log_arguments = []

        # skip invalid line (which means the line is not a valid log format)
        # a valid log has more than one terms (<Time> and/or <Argument> may be omitted)
        if len(terms) <= 1:
            line = f.readline()
            continue

        # log date format:
        # - `200112  3:08:09`                        (MySQL 5.5 ?)
        # - `2020-02-02T07:15:46.187564Z` (ISO 8601) (MySQL 5.7 ?)

        # detect the log date format
        if time_repattern.match(terms[1]):
            log_date = '{} {}'.format(terms[0], terms[1])
            last_date = log_date
            log_id = terms[2]
            log_command = terms[3]
            if 4 < len(terms):
                log_arguments = terms[4:]
                log_argument = ' '.join(log_arguments)
        elif iso8601_repattern.match(terms[0]):
            log_date = terms[0]
            last_date = log_date
            log_id = terms[1]
            log_command = terms[2]
            if 3 < len(terms):
                log_arguments = terms[3:]
                log_argument = ' '.join(log_arguments)
        # sometimes a log line doesn't contain a date
        else:
            log_date = last_date
            log_id = terms[0]
            log_command = terms[1]
            if 2 < len(terms):
                log_arguments = terms[2:]
                log_argument = ' '.join(log_arguments)

        # Query command (DDL, DML, ...: CREATE, UPDATE, SELECT, ......)
        if 0 < len(log_arguments):
            query_command = log_arguments[0]

        if query_command not in target_query_commands:
            line = f.readline()
            continue

        # Search and trace the target
        # Filter queries with 2-phases (because sql parsing is slower compared to just matching the text)
        # Filter Phase 1: Just text matching
        if (log_command in ['Execute', 'Query']) \
                and (target_table in log_argument) and (target_column in log_argument) \
                and (filter_column in log_argument) and (filter_value in log_argument):

            # Parse the SQL
            parsed = sqlparse.parse(log_argument)
            tokens = [ token for token in parsed[0].flatten() if not token.is_whitespace ]

            # debug
            #print('log_date:', log_date)
            #print('log_id:', log_id)
            #print('log_command:', log_command)
            #print('log_argument:', log_argument)
            #print('parsed: ', parsed)
            #for token in tokens:
            #    print(type(token), token.ttype, ':', token)
            #print('')

            # Filter Phase 2: Checking at WHERE
            matched = False

            filter_values = [filter_value, '"{}"'.format(filter_value), "'{}'".format(filter_value)]
            try:
                # FIXME: Workaround for INSERT
                if tokens[0].match(sqlparse.tokens.Token.Keyword.DML, 'INSERT'):
                    matched = True
                else:
                    for i in range(len(tokens)):
                        token = tokens[i]
                        if token.match(sqlparse.tokens.Token.Keyword, 'WHERE') \
                                and tokens[i + 1].match(sqlparse.tokens.Token.Name, filter_column) \
                                and tokens[i + 2].match(sqlparse.tokens.Token.Operator.Comparison, '=') \
                                and (tokens[i + 3].match(sqlparse.tokens.Token.Literal.Number.Integer, filter_values) \
                                    or tokens[i + 3].match(sqlparse.tokens.Token.Literal.String.Single, filter_values)):
                            matched = True
                            break
            except IndexError:
                pass

            if not matched:
                line = f.readline()
                continue

            # Trace the target column
            set_value = None
            inc_value = None
            try:
                if tokens[0].match(sqlparse.tokens.Token.Keyword.DML, 'INSERT'):
                    if not tokens[1].match(sqlparse.tokens.Token.Keyword, 'INTO'):
                        break
                    if not tokens[2].match(sqlparse.tokens.Token.Name, target_table):
                        break
                    if not tokens[3].match(sqlparse.tokens.Token.Punctuation, '('):
                        break
                    column_index = -1
                    index = 0
                    # FIXME: 2 is a magic number, replace it using search based on commas
                    for i in range(4, len(tokens), 2):
                        token = tokens[i]
                        # Note: sometimes a column name may be detected as Keyword, not Name
                        if (token.match(sqlparse.tokens.Token.Keyword, target_column) or token.match(sqlparse.tokens.Token.Name, target_column)):
                            column_index = index
                            break
                        index = index + 1
                    if 0 <= column_index:
                        for i in range(4, len(tokens)):
                            token = tokens[i]
                            if token.match(sqlparse.tokens.Token.Keyword, 'VALUES'):
                                index = 0
                                for j in range(i + 2, len(tokens), 2):
                                    if index == column_index:
                                        set_value = tokens[j].value
                                        break
                                    index = index + 1
                            if set_value is not None:
                                break

                elif tokens[0].match(sqlparse.tokens.Token.Keyword.DML, 'UPDATE'):
                    if not tokens[1].match(sqlparse.tokens.Token.Name, target_table):
                        break
                    if not tokens[2].match(sqlparse.tokens.Token.Keyword, 'SET'):
                        break
                    for i in range(3, len(tokens)):
                        token = tokens[i]
                        # Note: sometimes a column name may be detected as Keyword, not Name
                        if (token.match(sqlparse.tokens.Token.Keyword, target_column) or token.match(sqlparse.tokens.Token.Name, target_column)) \
                                and tokens[i + 1].match(sqlparse.tokens.Token.Operator.Comparison, '='):
                            # Patterns:
                            # - foo = 999       (set)
                            # - foo = foo + 999 (incremental)
                            # Does not care other cases so far FIXME
                            if (tokens[i + 2].match(sqlparse.tokens.Token.Keyword, target_column) or tokens[i + 2].match(sqlparse.tokens.Token.Name, target_column)):
                                if tokens[i + 3].match(sqlparse.tokens.Token.Operator, '+'):
                                    inc_value = int(tokens[i + 4].value)
                                elif tokens[i + 3].match(sqlparse.tokens.Token.Operator, '-'):
                                    inc_value = -1 * int(tokens[i + 4].value)
                            else:
                                set_value = tokens[i + 2].value

                        # If we reach another SQL keyword, stop searching any more
                        if token.match(sqlparse.tokens.Token.Keyword, 'WHERE'):
                            break
            except IndexError:
                pass

            if (set_value is None) and (inc_value is None):
                line = f.readline()
                continue

            # debug
            #print('set_value:', set_value)
            #print(type(set_value))
            #print('inc_value:', inc_value)
            #print(type(inc_value))
            #print('')

            hist = {
                'log_date': log_date,
                'log_id': log_id,
                'value': set_value,
                'increment': inc_value
            }

            # debug
            #print('hist:', hist)

            histories.append(hist)

        line = f.readline()


def search_from_file(filename, target_table, target_column, filter_column, filter_value):

    # Open with binary mode, because sometimes encoding errors occur
    if filename.endswith('.gz'):
        with gzip.open(filename, mode='rb') as f:
            search(f, target_table, target_column, filter_column, filter_value)
    else:
        with open(filename, mode='rb') as f:
            search(f, target_table, target_column, filter_column, filter_value)


def main():

    target_table = args.target_table
    target_column = args.target_column
    filter_column = args.filter_column
    filter_value = args.filter_value

    if args.log_file is not None:
        print('=== Searching in {} ==='.format(args.log_file))
        search_from_file(args.log_file, target_table, target_column, filter_column, filter_value)

    elif args.log_dir is not None:
        files = sorted(glob.glob(args.log_dir + '/*'))
        num_files = len(files)
        current = 1
        for log_file in files:
            print('=== Searching in {} ({}/{}) ==='.format(log_file, current, num_files))
            search_from_file(log_file, target_table, target_column, filter_column, filter_value)
            current += 1

    print('')
    for hist in histories:
        if hist['value'] is not None:
            print('{} {}.{} ({} = {}) is set: {}'.format(hist['log_date'], target_table, target_column, filter_column, filter_value, hist['value']))
        if hist['increment'] is not None:
            print('{} {}.{} ({} = {}) changes: {:+d}'.format(hist['log_date'], target_table, target_column, filter_column, filter_value, hist['increment']))


if __name__ == '__main__':
    main()
