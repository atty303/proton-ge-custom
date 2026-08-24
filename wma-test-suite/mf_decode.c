#define COBJMACROS

#include <fcntl.h>
#include <io.h>
#include <mfapi.h>
#include <mferror.h>
#include <mfidl.h>
#include <mfreadwrite.h>
#include <stdint.h>
#include <stdio.h>
#include <wchar.h>
#include <windows.h>


static void print_hresult(const char *operation, HRESULT hr)
{
    fprintf(stderr, "%s failed: %#lx\n", operation, hr);
}


int wmain(int argc, wchar_t **argv)
{
    IMFSourceReader *reader = NULL;
    IMFByteStream *byte_stream = NULL;
    IMFMediaType *requested_type = NULL, *current_type = NULL;
    FILE *output = NULL;
    UINT32 sample_rate = 0, channels = 0, bits = 0;
    uint64_t output_bytes = 0;
    HRESULT hr;
    int result = 1;

    if (argc != 3)
    {
        fwprintf(stderr, L"usage: mf-decode.exe INPUT.wma OUTPUT.s16le\n");
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
    if (FAILED(hr = MFCreateFile(MF_ACCESSMODE_READ, MF_OPENMODE_FAIL_IF_NOT_EXIST,
                                 MF_FILEFLAGS_NONE, argv[1], &byte_stream)))
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
        FAILED(hr = IMFMediaType_GetUINT32(current_type, &MF_MT_AUDIO_SAMPLES_PER_SECOND, &sample_rate)) ||
        FAILED(hr = IMFMediaType_GetUINT32(current_type, &MF_MT_AUDIO_NUM_CHANNELS, &channels)) ||
        FAILED(hr = IMFMediaType_GetUINT32(current_type, &MF_MT_AUDIO_BITS_PER_SAMPLE, &bits)))
    {
        print_hresult("get negotiated media type", hr);
        goto done;
    }
    if (bits != 16)
    {
        fprintf(stderr, "unexpected PCM depth: %u\n", bits);
        goto done;
    }
    if (!(output = _wfopen(argv[2], L"wb")))
    {
        fwprintf(stderr, L"could not open output: %ls\n", argv[2]);
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
            output_bytes += length;
            IMFMediaBuffer_Unlock(buffer);
            IMFMediaBuffer_Release(buffer);
            IMFSample_Release(sample);
        }
        if (flags & MF_SOURCE_READERF_ENDOFSTREAM) break;
    }
    if (fclose(output))
    {
        output = NULL;
        fprintf(stderr, "close failed\n");
        goto done;
    }
    output = NULL;
    printf("{\"status\":\"complete\",\"sample_rate\":%u,\"channels\":%u,"
           "\"bits_per_sample\":%u,\"pcm_bytes\":%llu}\n",
           sample_rate, channels, bits, (unsigned long long)output_bytes);
    result = 0;

done:
    if (output) fclose(output);
    if (current_type) IMFMediaType_Release(current_type);
    if (requested_type) IMFMediaType_Release(requested_type);
    if (reader) IMFSourceReader_Release(reader);
    if (byte_stream) IMFByteStream_Release(byte_stream);
    MFShutdown();
    CoUninitialize();
    return result;
}
