#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <signal.h>

#define BUFF 1024

extern char **environ;

void handle_sigint(int sig) {
    (void)sig;
    printf("\nroot# ");
    fflush(stdout);
}

char* cat(const char *filename, char *content, size_t *length) {
    FILE *file = fopen(filename, "r");
    if (!file) {
        perror("cat");
        return content;
    }
    char buffer[BUFF];

    while (fgets(buffer, sizeof(buffer), file)) {
        size_t line = strlen(buffer);
        char *temp = realloc(content, *length + line + 1);
        if (!temp) {
            perror("realloc");
            fclose(file);
            free(content);
            exit(EXIT_FAILURE);
        }
        content = temp;
        strcpy(content + *length, buffer);
        *length += line;
    }

    fclose(file);
    return content;
}

char* touch(const char *filename) {
    FILE *file = fopen(filename, "w");
    if (file == NULL) {
        perror("touch");
        return NULL;
    }
    fclose(file);
    return (char *)filename;
}

void ls(void) {
    DIR *dir;
    struct dirent *entry;
    dir = opendir(".");
    if (!dir) {
        perror("ls");
        return;
    }
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] != '.') {
            printf("%s\n", entry->d_name);
        }
    }
    closedir(dir);
}

void shell_chmod(char *args) {
    while (*args == ' ') args++;
    char *mode_str = strtok(args, " ");
    char *filename = strtok(NULL, "");

    if (!mode_str || !filename) {
        fprintf(stderr, "chmod: usage: chmod MODE FILE\n");
        return;
    }

    mode_t mode = strtol(mode_str, NULL, 8);
    if (chmod(filename, mode) == 0) {
        printf("Permissions of '%s' changed to %s\n", filename, mode_str);
    } else {
        perror("chmod");
    }
}

void shell_chown(char *args) {
    while (*args == ' ') args++;
    char *filename = args;
    if (!filename || *filename == '\0') {
        fprintf(stderr, "chown: usage: chown FILE\n");
        return;
    }

    uid_t uid = getuid();
    gid_t gid = getgid();

    if (chown(filename, uid, gid) == 0) {
        printf("Ownership of '%s' changed to UID %d and GID %d\n", filename, uid, gid);
    } else {
        perror("chown");
    }
}

int rmdir_recursive(const char *path) {
    DIR *dir = opendir(path);
    if (!dir) {
        // Not a directory, try to remove as file
        if (remove(path) != 0) {
            perror("remove");
            return -1;
        }
        return 0;
    }

    struct dirent *entry;
    char fullpath[1024];

    while ((entry = readdir(dir)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0)
            continue;

        snprintf(fullpath, sizeof(fullpath), "%s/%s", path, entry->d_name);

        if (rmdir_recursive(fullpath) != 0) {
            closedir(dir);
            return -1;
        }
    }

    closedir(dir);

    if (rmdir(path) != 0) {
        perror("rmdir");
        return -1;
    }

    return 0;
}

int main(void) {
    // Handle Ctrl+C gracefully
    signal(SIGINT, handle_sigint);

    char *content = malloc(1);
    size_t len = 0;
    if (!content) {
        perror("malloc");
        exit(EXIT_FAILURE);
    }
    content[0] = '\0';

    char input[BUFF];
    while (1) {
        printf("root@localhost:~# ");
        if (!fgets(input, BUFF, stdin)) break;
        input[strcspn(input, "\n")] = '\0';

        if (strncmp(input, "cat ", 4) == 0) {
            char *filename = input + 4;
            while (*filename == ' ') filename++;
            content = cat(filename, content, &len);
            printf("\n--- File Content ---\n%s\n", content);
        } else if (strcmp(input, "exit") == 0) {
            printf("Exiting...\n");
            break;
        } else if (strcmp(input, "ls") == 0) {
            ls();
        } else if (strcmp(input, "clear") == 0) {
            // Clear screen, clear scrollback, move cursor to top-left
            printf("\033[H\033[J\033[3J");
            fflush(stdout);
            continue; // Skip printing prompt again this loop
        } else if (strncmp(input, "cd ", 3) == 0) {
            char *path = input + 3;
            while (*path == ' ') path++;
            if (*path == '\0') {
                fprintf(stderr, "cd: missing operand\n");
            } else if (chdir(path) != 0) {
                perror("cd");
            }
        } else if (strncmp(input, "touch ", 6) == 0) {
            char *filename = input + 6;
            while (*filename == ' ') filename++;
            if (*filename == '\0') {
                fprintf(stderr, "touch: missing operand\n");
            } else {
                if (touch(filename) != NULL) {
                    printf("File '%s' created.\n", filename);
                }
            }
        } else if (strncmp(input, "rm ", 3) == 0) {
            char *filename = input + 3;
            while (*filename == ' ') filename++;
            if (*filename == '\0') {
                fprintf(stderr, "rm: missing operand\n");
            } else {
                if (remove(filename) == 0) {
                    printf("File '%s' removed.\n", filename);
                } else {
                    perror("rm");
                }
            }
        } else if (strncmp(input, "chmod ", 6) == 0) {
            shell_chmod(input + 6);
        } else if (strncmp(input, "chown ", 6) == 0) {
            shell_chown(input + 6);
        } else if (strncmp(input, "rmdir ", 6) == 0) {
            char *dirname = input + 6;
            while (*dirname == ' ') dirname++;
            if (*dirname == '\0') {
                fprintf(stderr, "rmdir: missing operand\n");
            } else {
                if (rmdir_recursive(dirname) != 0) {
                    fprintf(stderr, "rmdir: failed to remove '%s'\n", dirname);
                }
            }
        } else if (strncmp(input, "./", 2) == 0) {
            pid_t pid = fork();
            if (pid == 0) {
                // Child process
                char *argv_exec[] = {input, NULL};
                execve(input, argv_exec, environ);
                perror("execve failed");
                exit(1);
            } else if (pid > 0) {
                // Parent process
                int status;
                waitpid(pid, &status, 0);
            } else {
                perror("fork failed");
            }
        } else {
            printf("Unknown command: %s\n", input);
        }

        free(content);
        content = malloc(1);
        if (!content) {
            perror("malloc");
            exit(EXIT_FAILURE);
        }
        len = 0;
        content[0] = '\0';
    }

    free(content);
    return 0;
}
