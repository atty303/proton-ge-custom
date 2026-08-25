#define COBJMACROS

#include <fcntl.h>
#include <io.h>
#include <mfapi.h>
#include <mferror.h>
#include <mfidl.h>
#include <mfreadwrite.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include <windows.h>

struct decode_result
{
    UINT32 sample_rate;
    UINT32 channels;
    UINT32 bits;
    uint64_t output_bytes;
};


static void print_hresult(const char *operation, HRESULT hr)
{
    fprintf(stderr, "%s failed: %#lx\n", operation, hr);
}


static int decode_one(const wchar_t *input_path, const wchar_t *output_path,
                      struct decode_result *decode_result)
{
    IMFSourceReader *reader = NULL;
    IMFByteStream *byte_stream = NULL;
    IMFMediaType *requested_type = NULL, *current_type = NULL;
    FILE *output = NULL;
    HRESULT hr;
    int result = 1;

    if (FAILED(hr = MFCreateFile(MF_ACCESSMODE_READ, MF_OPENMODE_FAIL_IF_NOT_EXIST,
                                 MF_FILEFLAGS_NONE, input_path, &byte_stream)))
    {
        print_hresult("MFCreateFile", hr);
        goto done;
    }
    if (FAILED(hr = MFCreateSourceReaderFromByteStream(byte_stream, NULL, &reader)))
    {
        print_hresult("MFCreateSourceReaderFromByteStream", hr);
        goto done;
    }
    if (FAILED(hr = IMFSourceReader_SetStreamSelection(reader, MF_SOURCE_READER_ALL_STREAMS, FALSE)) ||
        FAILED(hr = IMFSourceReader_SetStreamSelection(reader, MF_SOURCE_READER_FIRST_AUDIO_STREAM, TRUE)))
    {
        print_hresult("IMFSourceReader_SetStreamSelection", hr);
        goto done;
    }
    if (FAILED(hr = MFCreateMediaType(&requested_type)) ||
        FAILED(hr = IMFMediaType_SetGUID(requested_type, &MF_MT_MAJOR_TYPE, &MFMediaType_Audio)) ||
        FAILED(hr = IMFMediaType_SetGUID(requested_type, &MF_MT_SUBTYPE, &MFAudioFormat_PCM)) ||
        FAILED(hr = IMFMediaType_SetUINT32(requested_type, &MF_MT_AUDIO_BITS_PER_SAMPLE, 16)) ||
        FAILED(hr = IMFSourceReader_SetCurrentMediaType(reader, MF_SOURCE_READER_FIRST_AUDIO_STREAM,
                                                        NULL, requested_type)))
    {
        print_hresult("set S16LE media type", hr);
        goto done;
    }
    if (FAILED(hr = IMFSourceReader_GetCurrentMediaType(reader, MF_SOURCE_READER_FIRST_AUDIO_STREAM,
                                                        &current_type)) ||
        FAILED(hr = IMFMediaType_GetUINT32(current_type, &MF_MT_AUDIO_SAMPLES_PER_SECOND,
                                            &decode_result->sample_rate)) ||
        FAILED(hr = IMFMediaType_GetUINT32(current_type, &MF_MT_AUDIO_NUM_CHANNELS,
                                            &decode_result->channels)) ||
        FAILED(hr = IMFMediaType_GetUINT32(current_type, &MF_MT_AUDIO_BITS_PER_SAMPLE,
                                            &decode_result->bits)))
    {
        print_hresult("get negotiated media type", hr);
        goto done;
    }
    if (decode_result->bits != 16)
    {
        fprintf(stderr, "unexpected PCM depth: %u\n", decode_result->bits);
        goto done;
    }
    if (!(output = _wfopen(output_path, L"wb")))
    {
        fwprintf(stderr, L"could not open output: %ls\n", output_path);
        goto done;
    }

    for (;;)
    {
        IMFSample *sample = NULL;
        IMFMediaBuffer *buffer = NULL;
        DWORD actual_stream = 0, flags = 0;
        LONGLONG timestamp = 0;
        BYTE *data = NULL;
        DWORD max_length = 0, length = 0;

        hr = IMFSourceReader_ReadSample(reader, MF_SOURCE_READER_FIRST_AUDIO_STREAM, 0,
                                        &actual_stream, &flags, &timestamp, &sample);
        if (FAILED(hr))
        {
            print_hresult("IMFSourceReader_ReadSample", hr);
            if (sample) IMFSample_Release(sample);
            goto done;
        }
        if (sample)
        {
            if (FAILED(hr = IMFSample_ConvertToContiguousBuffer(sample, &buffer)) ||
                FAILED(hr = IMFMediaBuffer_Lock(buffer, &data, &max_length, &length)))
            {
                print_hresult("read decoded sample", hr);
                if (buffer) IMFMediaBuffer_Release(buffer);
                IMFSample_Release(sample);
                goto done;
            }
            if (length && fwrite(data, 1, length, output) != length)
            {
                fprintf(stderr, "write failed\n");
                IMFMediaBuffer_Unlock(buffer);
                IMFMediaBuffer_Release(buffer);
                IMFSample_Release(sample);
                goto done;
            }
            decode_result->output_bytes += length;
            IMFMediaBuffer_Unlock(buffer);
            IMFMediaBuffer_Release(buffer);
            IMFSample_Release(sample);
        }
        if (flags & MF_SOURCE_READERF_ENDOFSTREAM) break;
    }

    {
        IMFSample *sample = NULL;
        DWORD actual_stream = 0, flags = 0;
        LONGLONG timestamp = 0;

        hr = IMFSourceReader_ReadSample(reader, MF_SOURCE_READER_FIRST_AUDIO_STREAM, 0,
                                        &actual_stream, &flags, &timestamp, &sample);
        if (FAILED(hr) || sample || !(flags & MF_SOURCE_READERF_ENDOFSTREAM))
        {
            fprintf(stderr, "post-EOS audio read failed: hr=%#lx sample=%p flags=%#lx\n",
                    hr, sample, flags);
            if (sample) IMFSample_Release(sample);
            goto done;
        }
    }
    if (fclose(output))
    {
        output = NULL;
        fprintf(stderr, "close failed\n");
        goto done;
    }
    output = NULL;
    result = 0;

done:
    if (output) fclose(output);
    if (current_type) IMFMediaType_Release(current_type);
    if (requested_type) IMFMediaType_Release(requested_type);
    if (reader) IMFSourceReader_Release(reader);
    if (byte_stream) IMFByteStream_Release(byte_stream);
    return result;
}


static int has_audio_extension(const wchar_t *name)
{
    const wchar_t *extension = wcsrchr(name, L'.');
    return extension && (!_wcsicmp(extension, L".wma") || !_wcsicmp(extension, L".asf"));
}


static void print_json_string(const wchar_t *value)
{
    int size = WideCharToMultiByte(CP_UTF8, 0, value, -1, NULL, 0, NULL, NULL);
    char *utf8;
    const unsigned char *cursor;

    if (!size || !(utf8 = malloc(size)))
    {
        fputs("null", stdout);
        return;
    }
    WideCharToMultiByte(CP_UTF8, 0, value, -1, utf8, size, NULL, NULL);
    putchar('"');
    for (cursor = (const unsigned char *)utf8; *cursor; ++cursor)
    {
        if (*cursor == '"' || *cursor == '\\') putchar('\\');
        if (*cursor < 0x20) printf("\\u%04x", *cursor);
        else putchar(*cursor);
    }
    putchar('"');
    free(utf8);
}


static void print_result(const wchar_t *artifact, const struct decode_result *result)
{
    fputs("{\"status\":\"complete\",\"artifact\":", stdout);
    print_json_string(artifact);
    printf(",\"sample_rate\":%u,\"channels\":%u,\"bits_per_sample\":%u,"
           "\"pcm_bytes\":%llu,\"post_eos_verified\":true}\n", result->sample_rate,
           result->channels, result->bits, (unsigned long long)result->output_bytes);
    fflush(stdout);
}


static int probe_video_eos(const wchar_t *input_path, const GUID *subtype, const char *format_name,
                           BOOL enable_video_processing)
{
    IMFSourceReader *reader = NULL;
    IMFByteStream *byte_stream = NULL;
    IMFMediaType *requested_type = NULL;
    IMFAttributes *attributes = NULL;
    unsigned int samples = 0;
    HRESULT hr;
    int result = 1;

    if ((enable_video_processing &&
         (FAILED(hr = MFCreateAttributes(&attributes, 1)) ||
          FAILED(hr = IMFAttributes_SetUINT32(attributes, &MF_SOURCE_READER_ENABLE_VIDEO_PROCESSING, TRUE)))) ||
        FAILED(hr = MFCreateFile(MF_ACCESSMODE_READ, MF_OPENMODE_FAIL_IF_NOT_EXIST,
                                 MF_FILEFLAGS_NONE, input_path, &byte_stream)) ||
        FAILED(hr = MFCreateSourceReaderFromByteStream(byte_stream, attributes, &reader)))
    {
        print_hresult("create video Source Reader", hr);
        goto done;
    }
    if (FAILED(hr = IMFSourceReader_SetStreamSelection(reader, MF_SOURCE_READER_ALL_STREAMS, FALSE)) ||
        FAILED(hr = IMFSourceReader_SetStreamSelection(reader, MF_SOURCE_READER_FIRST_VIDEO_STREAM, TRUE)) ||
        FAILED(hr = MFCreateMediaType(&requested_type)) ||
        FAILED(hr = IMFMediaType_SetGUID(requested_type, &MF_MT_MAJOR_TYPE, &MFMediaType_Video)) ||
        FAILED(hr = IMFMediaType_SetGUID(requested_type, &MF_MT_SUBTYPE, subtype)) ||
        FAILED(hr = IMFSourceReader_SetCurrentMediaType(reader, MF_SOURCE_READER_FIRST_VIDEO_STREAM,
                                                        NULL, requested_type)))
    {
        print_hresult("configure video output", hr);
        goto done;
    }

    for (;;)
    {
        IMFSample *sample = NULL;
        DWORD actual_stream = 0, flags = 0;
        LONGLONG timestamp = 0;

        hr = IMFSourceReader_ReadSample(reader, MF_SOURCE_READER_FIRST_VIDEO_STREAM, 0,
                                        &actual_stream, &flags, &timestamp, &sample);
        if (FAILED(hr))
        {
            print_hresult("read video sample", hr);
            if (sample) IMFSample_Release(sample);
            goto done;
        }
        if (sample)
        {
            ++samples;
            IMFSample_Release(sample);
        }
        if (flags & MF_SOURCE_READERF_ENDOFSTREAM)
            break;
    }

    {
        IMFSample *sample = NULL;
        DWORD actual_stream = 0, flags = 0;
        LONGLONG timestamp = 0;

        hr = IMFSourceReader_ReadSample(reader, MF_SOURCE_READER_FIRST_VIDEO_STREAM, 0,
                                        &actual_stream, &flags, &timestamp, &sample);
        if (FAILED(hr) || sample || !(flags & MF_SOURCE_READERF_ENDOFSTREAM))
        {
            fprintf(stderr, "post-EOS video read failed: hr=%#lx sample=%p flags=%#lx\n",
                    hr, sample, flags);
            if (sample) IMFSample_Release(sample);
            goto done;
        }
    }

    printf("{\"status\":\"complete\",\"media\":\"video\",\"format\":\"%s\",\"samples\":%u,"
           "\"post_eos_verified\":true}\n", format_name, samples);
    result = 0;

done:
    if (requested_type) IMFMediaType_Release(requested_type);
    if (attributes) IMFAttributes_Release(attributes);
    if (reader) IMFSourceReader_Release(reader);
    if (byte_stream) IMFByteStream_Release(byte_stream);
    return result;
}


static int decode_directory(const wchar_t *input_directory, const wchar_t *output_directory)
{
    WIN32_FIND_DATAW entry;
    HANDLE search;
    wchar_t input_path[MAX_PATH], output_path[MAX_PATH], pattern[MAX_PATH];
    unsigned int artifacts = 0, errors = 0;

    if (swprintf(pattern, MAX_PATH, L"%ls\\*", input_directory) < 0 ||
        (search = FindFirstFileW(pattern, &entry)) == INVALID_HANDLE_VALUE)
    {
        fwprintf(stderr, L"could not enumerate input directory: %ls\n", input_directory);
        return 1;
    }
    do
    {
        struct decode_result result = {0};
        if ((entry.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || !has_audio_extension(entry.cFileName))
            continue;
        ++artifacts;
        if (swprintf(input_path, MAX_PATH, L"%ls\\%ls", input_directory, entry.cFileName) < 0 ||
            swprintf(output_path, MAX_PATH, L"%ls\\%ls.s16le", output_directory,
                     entry.cFileName) < 0)
        {
            fprintf(stderr, "artifact path is too long\n");
            ++errors;
            continue;
        }
        if (decode_one(input_path, output_path, &result))
        {
            fputs("{\"status\":\"error\",\"artifact\":", stdout);
            print_json_string(entry.cFileName);
            fputs(",\"error_type\":\"candidate_decode_failed\"}\n", stdout);
            fflush(stdout);
            DeleteFileW(output_path);
            ++errors;
            continue;
        }
        print_result(entry.cFileName, &result);
    } while (FindNextFileW(search, &entry));
    FindClose(search);
    fprintf(stderr, "mf-decode batch complete: artifacts=%u errors=%u\n", artifacts, errors);
    return errors != 0;
}


int wmain(int argc, wchar_t **argv)
{
    struct decode_result result = {0};
    HRESULT hr;
    int return_code;

    if (argc != 3 && (argc != 4 || wcscmp(argv[1], L"--directory")))
    {
        fwprintf(stderr, L"usage: mf-decode.exe INPUT.wma OUTPUT.s16le\n"
                         L"       mf-decode.exe --directory INPUT_DIR OUTPUT_DIR\n"
                         L"       mf-decode.exe --video-eos INPUT_VIDEO\n"
                         L"       mf-decode.exe --video-eos-rgb32 INPUT_VIDEO\n");
        return 2;
    }
    if (FAILED(hr = CoInitializeEx(NULL, COINIT_MULTITHREADED)))
    {
        print_hresult("CoInitializeEx", hr);
        return 1;
    }
    if (FAILED(hr = MFStartup(MF_VERSION, MFSTARTUP_FULL)))
    {
        print_hresult("MFStartup", hr);
        CoUninitialize();
        return 1;
    }
    if (!wcscmp(argv[1], L"--video-eos"))
        return_code = probe_video_eos(argv[2], &MFVideoFormat_NV12, "NV12", FALSE);
    else if (!wcscmp(argv[1], L"--video-eos-rgb32"))
        return_code = probe_video_eos(argv[2], &MFVideoFormat_RGB32, "RGB32", TRUE);
    else if (argc == 4)
        return_code = decode_directory(argv[2], argv[3]);
    else if (!(return_code = decode_one(argv[1], argv[2], &result)))
        print_result(argv[1], &result);
    MFShutdown();
    CoUninitialize();
    return return_code;
}
